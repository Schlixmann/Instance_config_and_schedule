from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.instance import transform_ilp_to_branches, Instance
from src.ra_pst_py.simulator import Simulator, AllocationTypeEnum

from lxml import etree
import unittest
import json
import copy
import os


class InstanceTest(unittest.TestCase):
    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml",
        )
        self.instance = Instance(self.ra_pst, {}, id=1)

    def test_transform_ilp_to_branchmap(self):
        ra_pst = build_rapst(
            process_file="tests/test_data/test_instance_data/BPM_TestSet_10.xml",
            resource_file="tests/test_data/test_instance_data/(0.6, 0.4, 0.0)-random-3-uniform-resource_based-2-1-10.xml",
        )
        self.instance = Instance(ra_pst, {}, id=1)
        schedule_file = "tests/test_data/test_instance_data/(0.6, 0.4, 0.0)-random-3-uniform-resource_based-2-1-10.json"
        branches_to_apply = self.instance.transform_ilp_to_branchmap(schedule_file)
        target = {
            "a1": 0,
            "a2": 1,
            "a3": 0,
            "a4": 1,
            "a5": 1,
            "a6": 1,
            "a7": [],
            "a8": 0,
            "a9": 0,
            "a10": 0,
        }
        self.assertEqual(branches_to_apply, target)

    def test_get_optimal_instances(self):
        ra_pst = build_rapst(
            process_file="tests/test_data/test_instance_data/BPM_TestSet_10.xml",
            resource_file="tests/test_data/test_instance_data/(0.6, 0.4, 0.0)-random-3-uniform-resource_based-2-1-10.xml",
        )
        #show_tree_as_graph(ra_pst)
        for i in range(8):
            self.instance = Instance(copy.deepcopy(ra_pst), {}, id=i)
            schedule_file = "tests/test_data/test_instance_data/(0.6, 0.4, 0.0)-random-3-uniform-resource_based-2-1-10.json"
            optimal_instance = self.instance.get_optimal_instance_from_schedule(
                schedule_file=schedule_file
            )
            tree = etree.ElementTree(optimal_instance)
            etree.indent(tree, space="\t", level=0)
            tree.write("test.xml")

            tasks, jobs = compare_task_w_jobs(
                "test.xml", schedule_file, self.instance.id
            )
            self.assertEqual(len(tasks), len(jobs))


def compare_task_w_jobs(ra_pst, ilp, instance_id):
    tree = etree.parse(ra_pst)
    root = tree.getroot()
    ns = {"cpee1": list(root.nsmap.values())[0]}
    task_nodes = root.xpath(
        "//cpee1:call[not(ancestor::cpee1:children) and not(ancestor::cpee1:allocation)] | //cpee1:manipulate[not(ancestor::cpee1:children) and not(ancestor::cpee1:allocation)]",
        namespaces=ns,
    )

    with open(ilp, "r") as f:
        data = json.load(f)
    instance = data["instances"][instance_id]
    jobs = [jobId for jobId, job in instance["jobs"].items() if job["selected"]]
    selected_branches = [job["branch"] for jobId, job in instance["jobs"].items() if job["selected"]]
    deletes = [(branch["jobs"], branch["deletes"]) for branchId, branch in instance["branches"].items() if branchId in selected_branches]


    return task_nodes, jobs

class BranchTest(unittest.TestCase):
     def test_apply_branches(self):
        ra_pst = build_rapst(
            process_file="tests/test_data/test_process.xml",
            resource_file=f"tests/test_data/resource_cp_tests/insert_after_before.xml",
        )
        show_tree_as_graph(ra_pst)
        instance = Instance(ra_pst=ra_pst, branches_to_apply={}, id=0)
        for task_id in instance.ra_pst.get_tasklist(attribute="id"):
            branch = instance.ra_pst.get_branches()[task_id][0]
            allocated_ra_pst = branch.apply_to_process_refactor(instance)
        
        self.assertEqual(instance.ra_pst, allocated_ra_pst)
        show_tree_as_graph(instance.ra_pst)
        instance.ra_pst.save_ra_pst("test.xml")

