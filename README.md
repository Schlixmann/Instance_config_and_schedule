# Instance Configuration and Scheduling based on the Resource-Augmented Process Structure Tree

This Repo contains the code accompanying the publication named above. 

The evaluation can be found in the jupyter notebook 'evaluation.ipynb'
The raw data of the computational evaluation can be found in `testset_final_offline/<task_number>/evaluation/solution_approach` and `testsets_final_online/<task_number>/evaluation/solution_approach`.

The Constraint Programming and MIP formulations can be found in. 
`src/ra_pst_py/cp_docplex_decomposed` and `src/ra_pst_py/cp_docplex`

To use the scheduling formulations, an installation of CPLEX CPOptimizer and Gurobi is needed. 
Academic Licenses are available for both solvers.
You can have a look at the schedules of the evaluation by running: 
```
python -m src.ra_pst_py.cli.visualize_schedule <file_path>
```
for any file in the "evaluation" subdirectories

To re-run the experiments. Run `use_cases.py`. 
Attention: Run-time of all experiments is > 48h. 






