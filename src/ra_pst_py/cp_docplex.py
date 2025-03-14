from docplex.cp.model import *
import json
import gurobipy as gp
from gurobipy import GRB


context.solver.local.execfile = '/opt/ibm/ILOG/CPLEX_Studio2211/cpoptimizer/bin/x86-64_linux/cpoptimizer'


def cp_solver(ra_pst_json, warm_start_json=None, log_file = "cpo_solver.log", timeout=100, break_symmetries:bool=False, sigma:int=0):
    """
    ra_pst_json input format:
    {
        "resources": [resourceId],
        "instances": [
            {
                "tasks": { 
                    taskId: {
                        "branches": [branchId]
                    }
                },
                "resources": [resourceId],
                "branches": {
                    branchId: {
                        "task": taskId,
                        "jobs": [jobId],
                        "deletes": [taskId],
                        "branchCost": cost
                    }
                },
                "jobs": {
                    jobId: {
                        "branch": branchId,
                        "resource": resourceId,
                        "cost": cost,
                        "after": [jobId],
                        "instance": instanceId,
                        "min_start_time": int
                    }
                }
            }
        ]
    }
    """
    with open(ra_pst_json, "r") as f:
        ra_psts = json.load(f)
    
    if warm_start_json:
        with open(warm_start_json, "r") as f:
            warm_start_ra_psts = json.load(f)
    
    # Fix taskIds for deletes: 
    for i, instance in enumerate(ra_psts["instances"]):
        if "fixed" not in instance.keys():
            instance["fixed"] = False
    
    #-----------------------------------------------------------------------------
    # Build the model
    #-----------------------------------------------------------------------------

    model = CpoModel()
    job_intervals = []
    fixed_intervals = 0

    for ra_pst in ra_psts["instances"]:
        min_time = 0
        if ra_pst["fixed"]:
            # Create fixed intervals for selected jobs:
            for jobId, job in ra_pst["jobs"].items():
                if job["selected"]:
                    job["interval"] = model.interval_var(name=jobId, optional=False, size=int(job["cost"]))
                    # print(f'Add job {jobId}')
                    
                    # Fix intervals of Jobs scheduled in previous jobs:
                    if job["start"] is not None:
                        start_hr = int(job["start"])
                        end_hr = int(job["start"]) + int(job["cost"])
                        job["interval"].set_start_min(start_hr)
                        job["interval"].set_start_max(start_hr + sigma) 
                        job["interval"].set_end_min(end_hr)
                        job["interval"].set_end_max(end_hr + sigma)
                    fixed_intervals += 1
                    
                    # TODO figure out if this should be part of the objective or not
                    job_intervals.append(job["interval"])

        else:
            # Create optional interval variables for each job
            for jobId, job in ra_pst["jobs"].items():
                job["interval"] = model.interval_var(name=jobId, optional=True, size=int(job["cost"]))

                # Start time must be > than release time if a release time for instance is given
                if job["release_time"]:
                    min_time = job["release_time"]
                job["interval"].set_start_min(min_time)
                job_intervals.append(job["interval"])

        # Precedence constraints
        for jobId, job in ra_pst["jobs"].items():
            for jobId2 in job["after"]:
                if ra_pst["fixed"]:
                    if ra_pst["jobs"][jobId]["selected"] & ra_pst["jobs"][jobId2]["selected"]:
                        model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))
                else:    
                    model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))
                    
     # No overlap between jobs on the same resource   
    for r in ra_psts["resources"]:
        resource_intervals = []
        for ra_pst in ra_psts["instances"]:
            if ra_pst["fixed"]:
                resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if (job["resource"] == r and job["selected"])])
            else:
                resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r])
        if len(resource_intervals) > 0:
            model.add(no_overlap(resource_intervals))
    

    model.add(minimize(max([end_of(interval) for interval in job_intervals])))

    for ra_pst in ra_psts["instances"]:
        if ra_pst["fixed"]: continue
        for branchId, branch in ra_pst["branches"].items():
            independent_branches = []
            for branch_2_id, branch_2 in ra_pst["branches"].items():
                if branch_2["task"] == branch["task"] or branch["task"] in branch_2["deletes"]:
                    independent_branches.append(branch_2_id)
            # master_model.add(sum([ra_pst["branches"][b_id]["selected"] for b_id in independent_branches]) == 1)
            model.add(sum([presence_of(ra_pst["jobs"][ra_pst["branches"][b_id]["jobs"][0]]["interval"]) for b_id in independent_branches]) == 1)
            branch_jobs = []
            for jobId in branch["jobs"]:
                if len(branch_jobs) > 0:
                    model.add(equal(presence_of(ra_pst["jobs"][jobId]["interval"]), presence_of(ra_pst["jobs"][branch_jobs[-1]]["interval"])))
                branch_jobs.append(jobId)

    if warm_start_json:
        starting_solution = CpoModelSolution()
        for i, ra_pst in enumerate(ra_psts["instances"]):
            if not ra_pst["fixed"]:
                for jobId, job in ra_pst["jobs"].items():
                    interval_var = job["interval"]
                    warm_start_job = warm_start_ra_psts["instances"][i]["jobs"][jobId]
                    if warm_start_job["selected"]:
                        starting_solution.add_interval_var_solution(interval_var, start=warm_start_job["start"], end= warm_start_job["start"] + warm_start_job["cost"], size=warm_start_job["cost"], presence= warm_start_job["selected"])
                    else:
                        starting_solution.add_interval_var_solution(interval_var, start=warm_start_job["start"], end=None, size=warm_start_job["cost"], presence= warm_start_job["selected"])
        if len(starting_solution.get_all_var_solutions()) != len(model.get_all_variables())-fixed_intervals:
            raise ValueError(f"Solution size <{len(starting_solution.get_all_var_solutions())}> does not match model size <{len(model.get_all_variables())-fixed_intervals}>")
        model.set_starting_point(starting_solution)

    with open(log_file, "w") as f:
        result = model.solve(TimeLimit=timeout, log_output=f)

    if result.get_solve_status() == "Infeasible":
        raise ValueError("Infeasible model")
    intervals = []
    for ra_pst in ra_psts["instances"]:
        if not ra_pst["fixed"]:
            for jobId, job in ra_pst["jobs"].items():
                itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                job["selected"] = itv.is_present()
                job["start"] = itv.get_start()
                del job["interval"]

        else:
            for jobId, job in ra_pst["jobs"].items():
                if "interval" in job.keys():
                    itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                    job["selected"] = itv.is_present()
                    job["start"] = itv.get_start()
                    del job["interval"]
        ra_pst["fixed"] = True
    
        for jobId, job in ra_pst["jobs"].items():
            if job["selected"]:
                intervals.append(job)
    
    solve_details = result.get_solver_infos()
    total_interval_length = sum([element["cost"] for element in intervals])

    # Metadata per instance:
    ra_psts["instances"][-1]["solution"] = {
            "objective": result.get_objective_value(),
            "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
            "computing time": solve_details.get('TotalTime', 'N/A'),
            "solver status": result.get_solve_status(),
            "branches": solve_details.get('NumberOfBranches', 'N/A'),
            "propagations": solve_details.get('NumberOfPropagations','N/A'),
            "total interval length": total_interval_length,
            "lower_bound" : result.get_objective_bound()
        }


    if "solution" in ra_psts.keys():
        computing_time = ra_psts["solution"]["computing time"] + solve_details.get('TotalTime', 'N/A')
    else:
        computing_time = solve_details.get('TotalTime', 'N/A')
    ra_psts["solution"] = {
        "objective": result.get_objective_value(),
        "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
        "lower_bound" : result.get_objective_bound(),
        "computing time": computing_time,
        "solver status": result.get_solve_status(),
        "branches": solve_details.get('NumberOfBranches', 'N/A'),
        "propagations": solve_details.get('NumberOfPropagations','N/A'),
        "total interval length": total_interval_length
        #"objective_no_symmetry_breaking": result.get_objective_value() - alpha * sum([interval.get_size()[0] * presence_of(interval) for interval in job_intervals])
    }
    # TODO maybe add resource usage
    return ra_psts

    
def cp_solver_scheduling_only(ra_pst_json, warm_start_json=None, log_file = "cpo_solver.log", timeout=100, break_symmetries:bool=False, sigma:int=0):
    """ Only schedules predfined configurations [Config+ILP]
    ra_pst_json input format:
    {
        "resources": [resourceId],
        "instances": [
            {
                "tasks": { 
                    taskId: {
                        "branches": [branchId]
                    }
                },
                "resources": [resourceId],
                "branches": {
                    branchId: {
                        "task": taskId,
                        "jobs": [jobId],
                        "deletes": [taskId],
                        "branchCost": cost
                    }
                },
                "jobs": {
                    jobId: {
                        "branch": branchId,
                        "resource": resourceId,
                        "cost": cost,
                        "after": [jobId],
                        "instance": instanceId,
                        "min_start_time": int
                    }
                }
            }
        ]
    }
    """
    with open(ra_pst_json, "r") as f:
        ra_psts = json.load(f)
    
    if warm_start_json:
        with open(warm_start_json, "r") as f:
            warm_start_ra_psts = json.load(f)
    
    # Fix taskIds for deletes: 
    for i, instance in enumerate(ra_psts["instances"]):
        if "fixed" not in instance.keys():
            instance["fixed"] = False
        #inst_prefix = str(list(instance["tasks"].keys())[0]).split("-")[0]
        #for key, value in instance["branches"].items():
        #    value["deletes"] = [str(inst_prefix) + f"-{element}"for element in value["deletes"]]
    
    #-----------------------------------------------------------------------------
    # Build the model
    #-----------------------------------------------------------------------------

    model = CpoModel()
    job_intervals = []
    selected_jobs = []
    fixed_intervals = 0
    active_intervals = 0

    for ra_pst in ra_psts["instances"]:
        min_time = 0
        if ra_pst["fixed"]:
            # Create fixed intervals for selected jobs:
            for jobId, job in ra_pst["jobs"].items():
                if job["selected"]:
                    job["interval"] = model.interval_var(name=jobId, optional=False, size=int(job["cost"]))
                    # print(f'Add job {jobId}')
                    
                    # Fix intervals of Jobs scheduled in previous jobs:
                    if job["start"] is not None:
                        start_hr = int(job["start"])
                        end_hr = int(job["start"]) + int(job["cost"])
                        job["interval"].set_start_min(start_hr)
                        job["interval"].set_start_max(start_hr + sigma) 
                        job["interval"].set_end_min(end_hr)
                        job["interval"].set_end_max(end_hr + sigma)
                    #job_intervals.append(job["interval"])
                    fixed_intervals += 1
                    
                    # TODO figure out if this should be part of the objective or not
                    job_intervals.append(job["interval"])

        else:
            # Create optional interval variables for each job
            for jobId, job in ra_pst["jobs"].items():
                if job["selected"] == True:
                    job["interval"] = model.interval_var(name=jobId, optional=False, size=int(job["cost"]))
                    # Start time must be > than release time if a release time for instance is given
                    if job["release_time"]:
                        min_time = job["release_time"]
                    job["interval"].set_start_min(min_time)
                    active_intervals += 1
                    job_intervals.append(job["interval"])
                    selected_jobs.append(jobId)

                #else:
                #    job["interval"] = model.interval_var(name=jobId, optional=True, size=int(0))
                #    model.add(presence_of(job["interval"]) == 0)
                    

        # Precedence constraints
        precedence_counter = 0
        for jobId, job in ra_pst["jobs"].items():
            if not "interval" in job.keys(): continue
            for jobId2 in job["after"]:
                if jobId2 in selected_jobs:
                    if ra_pst["fixed"]:
                        if ra_pst["jobs"][jobId]["selected"] & ra_pst["jobs"][jobId2]["selected"]:
                            model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))
                    else:    
                        model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))
                        precedence_counter +=1
                        
     # No overlap between jobs on the same resource   
    for r in ra_psts["resources"]:
        resource_intervals = []
        for ra_pst in ra_psts["instances"]:
            if ra_pst["fixed"]:
                resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if (job["resource"] == r and job["selected"])])
            else:
                resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r if "interval" in job.keys()])
        if len(resource_intervals) > 0:
            model.add(no_overlap(resource_intervals))
    
    
    # model.add(no_overlap(job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r) for r in ra_pst["resources"])
    alpha = 0
    # Objective
    model.add(minimize(max([end_of(interval) for interval in job_intervals]) + alpha * sum([interval.get_size()[0] * presence_of(interval) for interval in job_intervals])))

    with open(log_file, "w") as f:
        result = model.solve(FailLimit=100000000, TimeLimit=timeout, log_output=f)
    # result.print_solution()
    if result.get_solve_status() == "Infeasible":
        raise ValueError("Infeasible model")
    intervals = []
    for ra_pst in ra_psts["instances"]:
        if not ra_pst["fixed"]:
            for jobId, job in ra_pst["jobs"].items():
                if not "interval" in job.keys(): continue
                itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                job["selected"] = itv.is_present()
                job["start"] = itv.get_start()
                del job["interval"]

        else:
            for jobId, job in ra_pst["jobs"].items():
                if "interval" in job.keys():
                    itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                    job["start"] = itv.get_start()
                    del job["interval"]
        ra_pst["fixed"] = True
    
        for jobId, job in ra_pst["jobs"].items():
            if job["selected"]:
                intervals.append(job)
    
    solve_details = result.get_solver_infos()
    total_interval_length = sum([element["cost"] for element in intervals])

    # Metadata per instance:
    ra_psts["instances"][-1]["solution"] = {
            "objective": result.get_objective_value(),
            "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
            "computing time": solve_details.get('TotalTime', 'N/A'),
            "solver status": result.get_solve_status(),
            "branches": solve_details.get('NumberOfBranches', 'N/A'),
            "propagations": solve_details.get('NumberOfPropagations','N/A'),
            "total interval length": total_interval_length,
            "lower_bound" : result.get_objective_bound()
        }


    if "solution" in ra_psts.keys():
        computing_time = ra_psts["solution"]["computing time"] + solve_details.get('TotalTime', 'N/A')
    else:
        computing_time = solve_details.get('TotalTime', 'N/A')
    ra_psts["solution"] = {
        "objective": result.get_objective_value(),
        "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
        "lower_bound" : result.get_objective_bound(),
        "computing time": computing_time,
        "solver status": result.get_solve_status(),
        "branches": solve_details.get('NumberOfBranches', 'N/A'),
        "propagations": solve_details.get('NumberOfPropagations','N/A'),
        "total interval length": total_interval_length
        #"objective_no_symmetry_breaking": result.get_objective_value() - alpha * sum([interval.get_size()[0] * presence_of(interval) for interval in job_intervals])
    }
    # TODO maybe add resource usage
    return ra_psts


if __name__ == "__main__":
    file = "cp_rep_test.json"    
    print("Start")
    #result = cp_solver_decomposed(file)
    #x = cp_solver_alternative(file, warm_start_json=None)
    #with open("alterna_out.json", "w") as f:
    #    json.dump(x, f)
    print("================= \n comparison \n=================")
    x = cp_solver(file)
    with open("alterna_out.json", "w") as f:
        json.dump(x, f, indent=2)