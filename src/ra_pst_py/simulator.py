from src.ra_pst_py.instance import Instance
from src.ra_pst_py.core import Branch, RA_PST
from src.ra_pst_py.cp_docplex import cp_solver, cp_solver_decomposed

from enum import Enum, StrEnum
from collections import defaultdict
import numpy as np
from lxml import etree
import json
import os
import time
import itertools


class AllocationTypeEnum(StrEnum):
    HEURISTIC = "heuristic"
    SINGLE_INSTANCE_CP = "single_instance_cp"
    SINGLE_INSTANCE_CP_WARM = "single_instance_cp_warm"
    ALL_INSTANCE_CP = "all_instance_cp"
    ALL_INSTANCE_CP_WARM = "all_instance_cp_warm"

class QueueObject():
    def __init__(self, instance: Instance, schedule_idx:int,  allocation_type: AllocationTypeEnum, task: etree._Element, release_time: float):
        self.instance = instance
        self.schedule_idx: int = schedule_idx
        self.allocation_type = allocation_type
        self.task = task
        self.release_time = release_time

class Simulator():
    def __init__(self, schedule_filepath: str = "out/sim_schedule.json", is_warmstart:bool = False) -> None:
        self.schedule_filepath = schedule_filepath
        # List of [{instance:RA_PST_instance, allocation_type:str(allocation_type)}]
        self.task_queue: list[QueueObject] = []  # List of QueueObject
        self.allocation_type: AllocationTypeEnum = None
        self.ns = None
        self.is_warmstart:bool = is_warmstart

    def add_instance(self, instance: Instance, allocation_type: AllocationTypeEnum):  # TODO
        """ 
        Adds a new instance that needs allocation
        """
        if self.is_warmstart: 
            schedule_idx = instance.id
        else:
            schedule_idx = len(self.task_queue)
        self.update_task_queue(QueueObject(
            instance, schedule_idx, allocation_type, instance.current_task, instance.release_time))
        #print(f"Instance added to simulator with allocation_type {allocation_type}")

    def set_namespace(self):
        # Check namespaces for ra-pst:
        if not self.ns:
            self.ns = self.task_queue[0].instance.ns
    
    def set_schedule_file(self):
        # Check/create schedule file:
        if not self.is_warmstart:
            os.makedirs(os.path.dirname(self.schedule_filepath), exist_ok=True)
            with open(self.schedule_filepath, "w"): pass

    def simulate(self):
        """
        TODO: refactor so that different allocation types are possible
        within one Simulator. e.g. Heuristic + single instance cp
        """
        # Prelims
        self.set_namespace()
        self.set_schedule_file()
        self.set_allocation_type()

        if self.allocation_type == AllocationTypeEnum.HEURISTIC:
            #Start taskwise allocation with process tree heuristic
            self.single_task_processing()
        elif self.allocation_type == AllocationTypeEnum.SINGLE_INSTANCE_CP:
            # Create ra_psts for next instance in task_queue
            self.single_instance_processing()
        elif self.allocation_type == AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM:
            # Create ra_psts for next instance in task_queue
            self.single_instance_processing(warmstart=True)
        elif self.allocation_type == AllocationTypeEnum.ALL_INSTANCE_CP:
            self.all_instance_processing()
        elif self.allocation_type == AllocationTypeEnum.ALL_INSTANCE_CP_WARM:
            self.all_instance_processing(warmstart=True)
        else:
            raise NotImplementedError(
                f"Allocation_type {self.allocation_type} has not been implemented yet")
        
    def get_current_instance_ilp_rep(self, schedule:dict, queue_object:QueueObject):
        if len(schedule["instances"]) > queue_object.schedule_idx:
            return schedule["instances"][queue_object.schedule_idx]
        else:
            return queue_object.instance.get_ilp_rep()

    def add_ilp_rep_to_schedule(self, ilp_rep:dict, schedule:dict, queue_object:QueueObject):
        if len(schedule["instances"]) > queue_object.schedule_idx:
            schedule["instances"][queue_object.schedule_idx] = ilp_rep
        else:
            schedule["instances"].append(ilp_rep)
            if schedule["instances"].index(ilp_rep) != queue_object.schedule_idx:
                raise ValueError(f'QueueObject.schedule_idx <{queue_object.schedule_idx}> does not match the position in Schedule["instances"] <{schedule["instances"].index(ilp_rep)}>')
        schedule["resources"] = list(set(schedule["resources"]).union(ilp_rep["resources"]))
        return schedule
    
    def save_schedule(self, schedule):
        with open(self.schedule_filepath, "w") as f:
            json.dump(schedule, f, indent=2)

    def add_branch_to_ilp_rep(self, branch:Branch, ilp_rep:dict, queue_object:QueueObject):
        task_id = branch.node.attrib["id"]
        branch_running_id = queue_object.instance.get_all_valid_branches_list().index(branch)
        branch_ilp_id = f"{queue_object.schedule_idx}-{task_id}-{branch_running_id}"
    
        branch_ilp_jobs = ilp_rep["branches"][branch_ilp_id]["jobs"]
        branch_ra_pst_tasks = branch.get_serialized_tasklist()

        if len(branch_ilp_jobs) != len(branch_ra_pst_tasks):
            raise ValueError(f"Length of Jobs in ilp_rep <{len(branch_ilp_jobs)}> does not match length of jobs in ra_pst_branch <{len(branch_ra_pst_tasks)}>")
        if len(queue_object.instance.get_all_valid_branches_list()) != len(ilp_rep["branches"]):
            raise ValueError
        #resource = branch.node.xpath("cpee1:children/cpee1:resource", namespaces=self.ns)[0].attrib["id"]
        for i, jobId in enumerate(branch_ilp_jobs):
            #if i == 0:
            #    if resource != ilp_rep["jobs"][jobId]["resource"]:
            #        raise ValueError(f"Resource <{resource}> != <{ilp_rep["jobs"][jobId]["resource"]}>")
            task = branch_ra_pst_tasks[i]
            start_time = float(task.xpath(
                "cpee1:expected_start", namespaces=self.ns)[0].text)
            end_time = float(task.xpath("cpee1:expected_end",
                             namespaces=self.ns)[0].text)
            duration = float(end_time) - float(start_time)

            ilp_rep["jobs"][jobId]["start"] = start_time
            ilp_rep["jobs"][jobId]["cost"] = duration
            ilp_rep["jobs"][jobId]["selected"] = True

        return ilp_rep
    
    def get_current_schedule_dict(self) -> dict:
        with open(self.schedule_filepath, "r+") as f:
            if os.path.getsize(self.schedule_filepath) > 0:
                schedule = json.load(f)
            else:
                # Default if file is empty
                schedule = {"instances": [],
                            "resources": [], 
                            "objective": 0}
        return schedule

    def single_task_processing(self):
        start = time.time()
        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            best_branch = queue_object.instance.allocate_next_task(self.schedule_filepath)
            if not best_branch.check_validity():
                raise ValueError("Invalid Branch chosen")

            schedule = self.get_current_schedule_dict()
            instance_ilp_rep = self.get_current_instance_ilp_rep(schedule, queue_object)
            instance_ilp_rep = self.add_branch_to_ilp_rep(best_branch, instance_ilp_rep, queue_object)
            schedule = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule, queue_object)
            queue_object.release_time = sum(queue_object.instance.times[-1])
            if queue_object.release_time > schedule["objective"]:
                schedule["objective"] = queue_object.release_time
            schedule["resources"] = list(set(schedule["resources"]).union(instance_ilp_rep["resources"]))
            self.save_schedule(schedule)
            if queue_object.instance.current_task != "end":
                self.update_task_queue(queue_object)

        end = time.time()
        self.add_allocation_metadata(float(end-start))

    
    def single_instance_processing(self, warmstart:bool = False):
        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            schedule_dict = self.get_current_schedule_dict()
            instance_ilp_rep = self.get_current_instance_ilp_rep(schedule_dict, queue_object)
            schedule_dict = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule_dict, queue_object)
            schedule_dict["resources"] = list(set(schedule_dict["resources"]).union(instance_ilp_rep["resources"]))
            if warmstart:
                self.create_warmstart_file(schedule_dict, [queue_object])
            self.save_schedule(schedule_dict)

            if warmstart:
                result = cp_solver(self.schedule_filepath, "tmp/warmstart.json")
            else:
                result = cp_solver(self.schedule_filepath)
            self.save_schedule(result)
        
    def all_instance_processing(self, warmstart:bool = False):
        # Generate dict needed for cp_solver
        for queue_object in self.task_queue:
            schedule_dict = self.get_current_schedule_dict()
            instance_ilp_rep = self.get_current_instance_ilp_rep(schedule_dict, queue_object)
            schedule_dict = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule_dict, queue_object)
            self.save_schedule(schedule_dict)
        
        if warmstart:
            self.create_warmstart_file(schedule_dict, self.task_queue)
            result = cp_solver(self.schedule_filepath, "tmp/warmstart.json")
        else:
            result = cp_solver_decomposed(self.schedule_filepath)
        self.save_schedule(result)
            
    def create_warmstart_file(self, ra_psts:dict, queue_objects:list[QueueObject]):
        with open("tmp/warmstart.json", "w") as f:
            ra_psts.setdefault("objective", 0)
            json.dump(ra_psts, f, indent=2)
        
        # Create new sim to create warmsstart file
        sim = Simulator(schedule_filepath="tmp/warmstart.json", is_warmstart=True)
        for queue_object in queue_objects:
            sim.add_instance(queue_object.instance, AllocationTypeEnum.HEURISTIC)
        sim.simulate()
        print("Warmstart file created")

    def update_task_queue(self, queue_object: QueueObject):
        # instance, allocation_type, task, release_time = task
        self.task_queue.append(queue_object)
        self.task_queue.sort(key=lambda object: object.release_time)

    def set_allocation_type(self):
        """
        Check that all instances are either instance wise allocation or
        Full Batch allocation. 
        """
        allocation_types = {item.allocation_type
                            for item in self.task_queue}
        # Determine the allocation type
        if allocation_types == {AllocationTypeEnum.HEURISTIC}:
            self.allocation_type = AllocationTypeEnum.HEURISTIC
        elif allocation_types == {AllocationTypeEnum.SINGLE_INSTANCE_CP}:
            self.allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_CP
        elif allocation_types == {AllocationTypeEnum.ALL_INSTANCE_CP}:
            self.allocation_type = AllocationTypeEnum.ALL_INSTANCE_CP
        elif allocation_types == {AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM}:
            self.allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM
        elif allocation_types == {AllocationTypeEnum.ALL_INSTANCE_CP_WARM}:
            self.allocation_type = AllocationTypeEnum.ALL_INSTANCE_CP_WARM
        else:
            raise NotImplementedError(f"The allocation type combination {allocation_types} is not implemented")

    def add_allocation_metadata(self, computing_time: float):
        with open(self.schedule_filepath, "r+") as f:
            ra_psts = json.load(f)
            intervals = []
            for ra_pst in ra_psts["instances"]:
                for jobId, job in ra_pst["jobs"].items():
                    if job["selected"]:
                        intervals.append({
                            "jobId": jobId,
                            "start": job["start"],
                            "duration": job["cost"]
                        })
            total_interval_length = sum(
                [element["duration"] for element in intervals])
            ra_psts["solution"] = {
                "objective": ra_psts["objective"],
                "computing time": computing_time,
                "total interval length": total_interval_length
            }
            # Save back to file
            f.seek(0)  # Reset file pointer to the beginning
            json.dump(ra_psts, f, indent=2)
            f.truncate()


if __name__ == "__main__":
    pass
