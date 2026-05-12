import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt

occurences = []
with open("Analysis/Modules.txt", "r") as file: 
    for line in file.readlines():
        occurences.append(int(line.strip().split(" ")[0]))

print(occurences)

values = [0 for i in range(max(occurences)+1)]
x = [i for i in range(len(values))]
for value in occurences:
    values[value] += 1

plot = sns.barplot(x=x, y=values)



plt.xticks(np.arange(0, len(values), 5))
plt.xlabel("Number of Modules")
plt.ylabel("Occurance")
plot.figure.show()
plot.figure.savefig("Modules.pdf")