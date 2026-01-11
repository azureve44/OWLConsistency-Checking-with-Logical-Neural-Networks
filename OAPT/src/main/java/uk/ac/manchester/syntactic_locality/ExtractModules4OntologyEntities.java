package uk.ac.manchester.syntactic_locality;

import java.io.File;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;

import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.io.RDFXMLOntologyFormat;
import org.semanticweb.owlapi.model.IRI;
import org.semanticweb.owlapi.model.OWLAxiom;
import org.semanticweb.owlapi.model.OWLEntity;
import org.semanticweb.owlapi.model.OWLOntology;
import org.semanticweb.owlapi.model.OWLOntologyCreationException;
import org.semanticweb.owlapi.model.OWLOntologyManager;

import uk.ac.manchester.cs.owl.owlapi.OWLClassImpl;


public class ExtractModules4OntologyEntities {

    private OWLOntologyManager externalOntologyManager;

    private OWLOntology ontoToModularize;

    // Don't forget the trainling slahes!!
    private String ontFilesPathPrefix = "/home/patrick/projects/2014/smallis/data/wo_imports/";
    private String resultModuleFilePath = "/tmp/module.owl";

    private List<String> fileNames = new ArrayList<String>(Arrays.asList(
            "basic.owl", "chebi_import.owl", "cl-basic.owl",
            "cl-bridge-to-fbbt.owl", "cl-bridge-to-fma.owl", "cl-bridge-to-ma.owl",
            "cl-bridge-to-wbbt.owl", "cl-bridge-to-zfa.owl", "cl_import.owl",
            "ctd_omim_mesh_bridge.owl", "doid_import.owl", "dpo-importer.owl",
            "dpo.owl", "extra.owl", "fbbt_import.owl", "fbbt_phenotype.owl",
            "fma_import.owl", "go-plus.owl", "go_extensions__chebi_import.owl",
            "go_extensions__pato_import.owl", "go_extensions__pr_import.owl",
            "go_extensions__ro_import.owl", "go_extensions__uberon_import.owl",
            "go_import.owl", "go_phenotype.owl", "hp-importer.owl", "hp.owl",
            "hsapdv_import.owl", "human-genes.owl", "mammal.owl", "merged.owl",
            "metazoa.owl", "monarch.owl", "mp-edit.owl", "mp-importer.owl", "mp.owl",
            "mp_hp-align-equiv.owl", "mpath_import.owl", "mpath_phenotype.owl",
            "nbo_import.owl", "nbo_phenotype.owl", "ncbitaxon_import.owl",
            "pato.owl", "pato_import.owl", "po_import.owl", "pr_import.owl",
            "ro_extra.owl", "ro_import.owl", "ro_pending.owl", "so.owl",
            "so_import.owl", "uberon-bridge-to-fbbt.owl", "uberon-bridge-to-fma.owl",
            "uberon-bridge-to-ma.owl", "uberon-bridge-to-nifstd.owl",
            "uberon-bridge-to-wbbt.owl", "uberon-bridge-to-zfa.owl",
            "uberon_import.owl", "uberon_phenotype.owl", "vertebrate-curated.owl",
            "vertebrate.owl", "wbbt_import.owl",
            "wbphenotype-equivalence-axioms-subq-ubr.owl", "wbphenotype-importer.owl",
            "wbphenotype.owl", "x-disjoint.owl", "zfa.owl", "zp-importer.owl", "zp.owl"
            ));

    private static final String defaultModuleIRI = "http://dl-learner.org/ontologies/module_";
    private OWLOntology module;
    private IRI physicalModuleIRI;
    private IRI moduleIRI;
    private ModuleExtractor extractor;

    // classes from MGI_Geno_Disease.rpt/MGI_Geno_NotDisease.rpt
    private List<OWLEntity> entities = new ArrayList<OWLEntity>(Arrays.asList(
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000188"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000313"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000727"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000813"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000849"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001119"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001127"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001145"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001262"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001265"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001392"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001399"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001426"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001524"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001559"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001759"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001762"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001844"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001845"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001869"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001876"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001922"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001926"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002064"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002078"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002082"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002083"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002136"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002145"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002216"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002679"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002687"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002727"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002784"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002790"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002869"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002871"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002882"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002893"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003077"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003562"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003564"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003698"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003699"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004031"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004803"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004804"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004852"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005042"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005078"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005094"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005185"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005215"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005217"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005264"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005325"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005351"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005466"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005527"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005536"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005559"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005580"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0006387"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0006413"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008071"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008075"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008076"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008078"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008470"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008578"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008600"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008874"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0009008"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0009172"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0011088"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0011320"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0011353"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0011409"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0011425")))
        )); 

    public ExtractModules4OntologyEntities() throws URISyntaxException, OWLOntologyCreationException{
        loadExternalOntology();

        initExtractor();

        OWLOntologyManager man = OWLManager.createOWLOntologyManager();
        OWLOntology modules = man.createOntology();

        for (OWLEntity ent : entities) {
            moduleIRI = IRI.create(defaultModuleIRI + getEntityLabel(ent.getIRI().toString()) + ".owl");
            Set<OWLAxiom> axioms = extractor.extractModuleAxiomsForEntity(ent);
            module = extractor.getModuleFromAxioms(axioms, moduleIRI);
            man.addAxioms(modules, module.getAxioms());
        }

        physicalModuleIRI = IRI.create(new File(resultModuleFilePath));
        saveModuleToPhysicalIRI();
    }

    private void loadExternalOntology() throws OWLOntologyCreationException {
        externalOntologyManager = OWLManager.createOWLOntologyManager();
        ontoToModularize = externalOntologyManager.createOntology();

        for (String fileName : fileNames) {
            String filePath = ontFilesPathPrefix + fileName;
            OWLOntologyManager tmpMan = OWLManager.createOWLOntologyManager();
            OWLOntology tmpOnt = tmpMan.loadOntologyFromOntologyDocument(new File(filePath));
            externalOntologyManager.addAxioms(ontoToModularize, tmpOnt.getAxioms());
        }
    }

    private void saveModuleToPhysicalIRI() {
        try {
            externalOntologyManager.saveOntology(module, new RDFXMLOntologyFormat(), physicalModuleIRI);
        } catch (Exception e) {
            System.err.println("Error saving module\n" + e.getLocalizedMessage());
            e.printStackTrace();
        }
    }

    private void initExtractor(){
        //Bottom module
        boolean dualConcepts=false;
        boolean dualRoles=false;
        extractor = new ModuleExtractor(ontoToModularize, dualConcepts, dualRoles);
    }

    private String getEntityLabel(String iriStr){
        if (iriStr.indexOf("#")>=0)
            return iriStr.split("#")[1];
        return iriStr;
    }

    public static void main(String[] args) throws URISyntaxException, OWLOntologyCreationException {
        new ExtractModules4OntologyEntities();
    }
}
