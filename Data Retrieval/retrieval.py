import requests
from tqdm import tqdm
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
api_key = os.getenv("BioPortal_API")
base_url = "https://data.bioontology.org/ontologies"
output_path = Path(__file__).parent.parent / "data" / "ontologies"
print(api_key)
# Make a GET request to retrieve all ontologies
response = requests.get(base_url, params={'apikey': api_key})

# Check if the request was successful
if response.status_code == 200:
    ontologies = response.json()
    for ontology in ontologies:
        print(ontology['name'], ontology['acronym'])
else:
    print(f"Error: {response.status_code}")


downloaded_ontologies = [i.replace(".owl", "") for i in os.listdir(output_path)]
print(downloaded_ontologies)
indicies = []




unable_to_download : int = 0
for i in tqdm(range(0, 10)):
#for i in tqdm(range(0, 3)):
    if ontologies[i]["acronym"] in downloaded_ontologies: 
        continue
    response = requests.get(ontologies[i]["links"]["download"], params={'apikey': api_key, "download_format" : "rdf"})
    if response.status_code == 200:
    # Save the OWL content to a file
        with open(output_path / f"{ontologies[i]['acronym']}.owl", "wb") as file:
            file.write(response.content)
    else:
        unable_to_download += 1
print(f"Could not download {unable_to_download} ontologies.")