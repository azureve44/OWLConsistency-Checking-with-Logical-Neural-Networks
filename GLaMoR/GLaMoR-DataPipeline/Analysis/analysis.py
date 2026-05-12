import pandas as pd 
import numpy as np
import seaborn as sns


classes = pd.read_csv("Analysis/src/main/output/classes")["number"]
properties = pd.read_csv("Analysis/src/main/output/properties")["number"]



def _find_stats(file):
    sorted_list = (sorted(file.values))

    print(f"Mean: {np.mean(sorted_list)}")
    print(f"Median: {np.median(sorted_list)}")
    print(f"Standard Deviation: {np.std(sorted_list)}")


print("Classes:")
_find_stats(classes)
print("Properties")
_find_stats(properties)

for frame in [classes, properties]:
    values = pd.DataFrame([0 for i in range(max(frame)+1)])
    for entry in frame:
        values.iloc[entry] +=1
    x = [i for i in range(max(frame)+1)]
    
    plot = sns.lineplot(values)
    
    print(plot)
    plot.figure.savefig("stat.pdf")


