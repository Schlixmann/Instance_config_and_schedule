from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.instance import transform_ilp_to_branches, Instance
from src.ra_pst_py.brute_force import BruteForceSearch
from src.ra_pst_py.cp_google_or import conf_cp, conf_cp_scheduling
from src.ra_pst_py.cp_docplex import cp_solver

from lxml import etree
import unittest
import json



class CPTest(unittest.TestCase):

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
    
    def test_cp(self):
        result = conf_cp("tests/test_data/ilp_rep2.json")
        print([branch for branch in result["branches"] if branch["selected"] == 1])
        print(result["objective"])
        self.assertEqual(result["objective"], 59)
        #show_tree_as_graph(self.ra_pst)

    def test_cp_sched(self):
        #show_tree_as_graph(self.ra_pst)
        result = conf_cp_scheduling("tests/test_data/ilp_rep.json")
        with open("out/cp_result.json", "w") as f:
            json.dump(result, f, indent=2)
        #print([branch for branch in result["branches"] if branch["selected"] == 1])
        #print(result["objective"])
        #self.assertEqual(result["objective"], 59)
        #show_tree_as_graph(self.ra_pst)


class DocplexTest(unittest.TestCase):
    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
        self.ra_pst = build_rapst(
            process_file="test_instances/instance_generator_process.xml",
            resource_file="test_instances/instance_generator_resources.xml"
        )
        ilp_rep = self.ra_pst.get_ilp_rep()
        ilp_dict = {"instances" : []}
        ilp_dict["instances"].append(ilp_rep)
        ilp_dict["resources"] = ilp_rep["resources"]
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_dict, f, indent=2)
            f.close()
    
    def test_cp(self):
        self.setUp()
        result = cp_solver("tests/test_data/ilp_rep.json")
        # print([branch for branch in result["branches"] if branch["selected"] == 1])
        print(result["objective"])
        with open("tests/test_data/cp_result.json", "w") as f:
            json.dump(result, f, indent=2)
        self.assertEqual(result["objective"], 59)
        #show_tree_as_graph(self.ra_pst)
    
    def test_multiple_cp(self):
        self.setUp()
        ra_psts = {}
        ra_psts["instances"] = []
        for i in range(10):
            ilp_rep = self.ra_pst.get_ilp_rep(instance_id=f'i{i+1}')
            ra_psts["instances"].append(ilp_rep)
        ra_psts["resources"] = ilp_rep["resources"]
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ra_psts, f, indent=2)
        result = cp_solver("tests/test_data/ilp_rep.json")
        # print([branch for branch in result["branches"] if branch["selected"] == 1])
        print(result["objective"])
        with open("tests/test_data/cp_result.json", "w") as f:
            json.dump(result, f, indent=2)

