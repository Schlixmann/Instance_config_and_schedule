from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator, AllocationTypeEnum
from src.ra_pst_py.heuristic import TaskAllocator
from src.ra_pst_py.instance import Instance
from src.ra_pst_py.cp_docplex import cp_solver_scheduling_only
from src.ra_pst_py.cp_docplex_decomposed import cp_subproblem

from lxml import etree
import unittest
import json
import copy
import time

class ScheduleTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches_sched.xml"
        )

        ilp_rep = self.ra_pst.get_ilp_rep()
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_rep, f, indent=2)
            f.close()
    
    def test_single_task_heuristic(self):
        release_times = [0,1,2]
        allocation_type = AllocationTypeEnum.HEURISTIC
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file, sigma=0, time_limit=10)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {},id=i, release_time=release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 72
        self.assertEqual(objective, target, "HEURISTIC: The found objective does not match the target value")

    def test_single_instance_heuristic(self):
        release_times = [0,1,2]
        # Heuristic Single Task allocation
        #show_tree_as_graph(self.ra_pst)
        allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_HEURISTIC
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file, sigma=0, time_limit=10)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {},id=i, release_time=release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 70
        self.assertEqual(objective, target, "HEURISTIC: The found objective does not match the target value")
        

    def test_multiinstance_cp_sim(self):

        #show_tree_as_graph(self.ra_pst)
        release_times = [0 for _ in range(8)]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.ALL_INSTANCE_CP
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file, sigma=0, time_limit=10)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, id=i, release_time=release_time)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 115
        self.assertEqual(objective, target, "ALL_INSTANCE_CP: The found objective does not match the target value")
    
        
    def test_single_instance_sim(self):
        #show_tree_as_graph(self.ra_pst)
        release_times = [0,0,0]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_CP
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file, sigma=0, time_limit=10)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, id=i, release_time=release_time)
            sim.add_instance(instance, allocation_type)

        start = time.time()
        sim.simulate()
        end = time.time()
        print("Elapsed time: ", end-start)
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 70
        self.assertEqual(objective, target, "SINGLE_INSTANCE_CP: The found objective does not match the target value")


    def test_ilp_sched(self):
        release_times = [0,1]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_ILP
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file, sigma=0, time_limit=10)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, id=i, release_time=release_time)
            sim.add_instance(instance, allocation_type)

        start = time.time()
        sim.simulate()
        end = time.time()
        print("Elapsed time: ", end-start)
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 65
        self.assertEqual(objective, target, "SINGLE_INSTANCE_CP: The found objective does not match the target value")

    def test_multiinstance_cp_decomposed(self):

        sched = None
        release_times = [0,1,2,4,5,6,7,8,9]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.ALL_INSTANCE_CP_DECOMPOSED
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file, sigma=0, time_limit=10)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched, id=i, release_time=release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 130
        #self.assertEqual(objective, target, "ALL_INSTANCE_CP: The found objective does not match the target value")

    def test_multiinstance_ilp(self):

        sched = None
        release_times = [0,1,2,4,5,6,7,8,9]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.ALL_INSTANCE_ILP
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file, sigma=0, time_limit=10)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, id=i, release_time=release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 240
        self.assertEqual(objective, target, "ALL_INSTANCE_CP: The found objective does not match the target value")


    def test_single_instance_cp_decomposed(self):
        release_times = [0,1,2]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_CP_DECOMPOSED
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file, sigma=0, time_limit=10)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, id=i, release_time=release_time)
            #instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)

        start = time.time()
        sim.simulate()
        end = time.time()
        print("Elapsed time: ", end-start)
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 70
        self.assertEqual(objective, target, "SINGLE_INSTANCE_CP: The found objective does not match the target value")


    def test_ilp_scheduling_vs_subproblem(self):
        schedule_file = "tests/test_comparison_data/cp_sched_vs_sub/schedule_all_instance_ilp.json"
        result_sched = cp_solver_scheduling_only(schedule_file)

        with open(schedule_file, "r") as f:
            schedule_dict = json.load(f)
        
        branches = set()
        #schedule_dict = cp_solver_scheduling_only(self.schedule_filepath, timeout=100, sigma=self.sigma)
        for instance in schedule_dict["instances"]:
            instance["fixed"]=False
            for jobId, job in instance["jobs"].items():
                job["fixed"]=False
                if job["selected"]:
                    for branchId, branch in instance["branches"].items():
                        if jobId in branch["jobs"]:
                            branch["selected"] = True
                            branches.add(branchId)

        result_sub, all_jobs = cp_subproblem(schedule_dict, branches)
        solve_details = result_sub.get_solver_infos()
        print(f"CP_Sched: {result_sched['solution']['objective']} in {result_sched['solution']['computing time']}, Subproblem: {result_sub.get_objective_value()} in {solve_details.get('TotalTime', 'N/A')}")