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


public class ExtractModules4OntologyEntities2 {

    private OWLOntologyManager externalOntologyManager;

    private OWLOntology ontoToModularize;

    // Don't forget the trainling slahes!!
    private String ontFilesPathPrefix = "/home/patrick/projects/2014/smallis/data/wo_imports/";
    private String resultModuleFilePath = "/tmp/module2.owl";

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

    // classes from MGI_GenePheno.rpt/Normal_MPannot_V2.csv
    private List<OWLEntity> entities = new ArrayList<OWLEntity>(Arrays.asList(
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000186"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000188"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000208"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000218"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000351"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000358"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000623"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000688"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000709"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000714"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000753"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000755"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0000921"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001186"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001260"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001263"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001513"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001552"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001559"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001577"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001625"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001805"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001844"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001845"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001846"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001861"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001869"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001870"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0001873"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002006"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002023"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002078"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002083"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002145"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002169"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002408"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002432"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002444"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002451"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002651"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002727"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002743"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002833"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002869"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002870"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002874"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0002875"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003009"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003059"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003077"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003179"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003339"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003341"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003504"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003562"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003631"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003632"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003725"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0003726"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004031"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004392"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004801"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004803"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004804"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0004974"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005010"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005013"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005015"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005018"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005042"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005092"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005179"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005215"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005293"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005331"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005367"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005369"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005370"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005371"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005375"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005376"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005377"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005378"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005379"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005380"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005381"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005382"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005384"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005385"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005386"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005387"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005388"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005389"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005390"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005391"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005394"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005397"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005463"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005491"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005515"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005566"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005580"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0005658"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0006082"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0006413"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008074"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008075"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008078"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008102"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008247"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008566"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008567"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008699"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008721"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008873"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008874"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0008880"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0009168"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0009171"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0009176"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0010378"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0010768"))),
            new OWLClassImpl(IRI.create(new URI("http://purl.obolibrary.org/obo/MP_0010771")))
        )); 

    public ExtractModules4OntologyEntities2() throws URISyntaxException, OWLOntologyCreationException{
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
        new ExtractModules4OntologyEntities2();
    }
}
