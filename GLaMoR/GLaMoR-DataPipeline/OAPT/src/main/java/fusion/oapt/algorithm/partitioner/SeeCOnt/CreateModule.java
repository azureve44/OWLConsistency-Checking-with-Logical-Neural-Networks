
package fusion.oapt.algorithm.partitioner.SeeCOnt;

import java.io.BufferedOutputStream;
import java.io.FileInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Set;
import java.util.zip.GZIPInputStream;

import fusion.oapt.algorithm.partitioner.SeeCOnt.moduleExtractor.Extractor;
import fusion.oapt.algorithm.partitioner.SeeCOnt.moduleExtractor.ModuleExtractor;
import fusion.oapt.general.cc.Coordinator;
import fusion.oapt.general.cc.ModelBuild;
import fusion.oapt.model.ext.sentence.RDFSentence;
import fusion.oapt.model.ext.sentence.RDFSentenceGraph;
import fusion.oapt.model.ext.sentence.filter.OntologyHeaderFilter;
import fusion.oapt.model.ext.sentence.filter.PureSchemaFilter;
import fusion.oapt.model.Node;
import fusion.oapt.model.NodeList;

import org.apache.jena.ontology.ConversionException;
import org.apache.jena.ontology.OntClass;
import org.apache.jena.ontology.OntDocumentManager;
import org.apache.jena.ontology.OntModel;
import org.apache.jena.ontology.OntModelSpec;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.Property;
import org.apache.jena.rdf.model.RDFNode;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.rdf.model.Statement;
import org.apache.jena.rdf.model.StmtIterator;
import org.apache.jena.reasoner.Reasoner;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.riot.RiotException;
import org.apache.jena.shared.BadURIException;
import org.apache.jena.vocabulary.OWL;


import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.io.StreamDocumentSource;
import org.semanticweb.owlapi.formats.RDFXMLDocumentFormat;
import org.semanticweb.owlapi.model.AddAxiom;
import org.semanticweb.owlapi.model.AddOntologyAnnotation;
import org.semanticweb.owlapi.model.MissingImportHandlingStrategy;
import org.semanticweb.owlapi.model.AxiomType;
import org.semanticweb.owlapi.model.IRI;
import org.semanticweb.owlapi.model.OWLAnnotation;
import org.semanticweb.owlapi.model.OWLAnnotationAssertionAxiom;
import org.semanticweb.owlapi.model.OWLAxiom;
import org.semanticweb.owlapi.model.OWLClass;
import org.semanticweb.owlapi.model.OWLClassAxiom;
import org.semanticweb.owlapi.model.OWLClassExpression;
import org.semanticweb.owlapi.model.OWLDataFactory;
import org.semanticweb.owlapi.model.OWLDataProperty;
import org.semanticweb.owlapi.model.OWLDataPropertyDomainAxiom;
import org.semanticweb.owlapi.model.OWLDataPropertyExpression;
import org.semanticweb.owlapi.model.OWLDataPropertyRangeAxiom;
import org.semanticweb.owlapi.model.OWLDeclarationAxiom;
import org.semanticweb.owlapi.model.OWLDocumentFormat;
import org.semanticweb.owlapi.model.OWLEntity;
import org.semanticweb.owlapi.model.OWLFunctionalObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLIndividual;
import org.semanticweb.owlapi.model.OWLInverseFunctionalObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLIrreflexiveObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLObjectProperty;
import org.semanticweb.owlapi.model.OWLObjectPropertyDomainAxiom;
import org.semanticweb.owlapi.model.OWLObjectPropertyExpression;
import org.semanticweb.owlapi.model.OWLObjectPropertyRangeAxiom;
import org.semanticweb.owlapi.model.OWLOntology;
import org.semanticweb.owlapi.model.OWLOntologyLoaderConfiguration;
import org.semanticweb.owlapi.model.OWLOntologyCreationException;
import org.semanticweb.owlapi.model.OWLOntologyManager;
import org.semanticweb.owlapi.model.OWLOntologyStorageException;
import org.semanticweb.owlapi.model.parameters.Imports;
import org.semanticweb.owlapi.model.OWLReflexiveObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLSymmetricObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLTransitiveObjectPropertyAxiom;

import org.semanticweb.owlapi.search.EntitySearcher;

import uk.ac.manchester.cs.owlapi.modularity.ModuleType;


public class CreateModule {
	private static final boolean USE_MERGED_EXTRACTION_SOURCE =
			readBooleanFlag("oapt.mergeExtractionSource", "OAPT_MERGE_EXTRACTION_SOURCE", false);
        private static final boolean ENABLE_MODULE_OVERLAP_DIAGNOSTICS =
                        readBooleanFlag("oapt.moduleOverlapDiagnostics", "OAPT_MODULE_OVERLAP_DIAGNOSTICS", true);
        private static final boolean ENABLE_TINY_CLUSTER_TIGHTENING =
                        readBooleanFlag("oapt.tightenTinyModules", "OAPT_TIGHTEN_TINY_MODULES", false);
        private static final int TINY_CLUSTER_MAX_SIZE =
                        readIntFlag("oapt.tinyClusterMaxSize", "OAPT_TINY_CLUSTER_MAX_SIZE", 100);
        private static final double TINY_CLUSTER_INFLATION_TRIGGER =
                        readDoubleFlag("oapt.tinyClusterInflationTrigger", "OAPT_TINY_CLUSTER_INFLATION_TRIGGER", 10.0d);
        private static final double TINY_CLUSTER_MIN_REDUCTION =
                        readDoubleFlag("oapt.tinyClusterMinReduction", "OAPT_TINY_CLUSTER_MIN_REDUCTION", 0.20d);
        private static final int OVERLAP_TOP_PAIR_LIMIT =
                        readIntFlag("oapt.moduleOverlapTopPairs", "OAPT_MODULE_OVERLAP_TOP_PAIRS", 20);
        private static final double NEAR_DUPLICATE_JACCARD =
                        readDoubleFlag("oapt.moduleNearDuplicateJaccard", "OAPT_MODULE_NEAR_DUPLICATE_JACCARD", 0.85d);
        private static final double NEAR_DUPLICATE_CONTAINMENT =
                        readDoubleFlag("oapt.moduleNearDuplicateContainment", "OAPT_MODULE_NEAR_DUPLICATE_CONTAINMENT", 0.90d);
	private  LinkedHashMap<Integer, Cluster> clusters; 
	private OntModel model; 
	private OWLOntology owl;
	private  String ontName = null;
	public static String tempDir = null;
	public static ArrayList<OntModel> models ;
	private LinkedHashMap<String, Integer> uriToClusterID = null;
	public static  int [][] NumLickConcept=null;
	private int numEntity;
	public static int [] numAloneElemnt;
	public static double[] numTree;
	ModelBuild MB;
	public  ArrayList<String> modelNames ;
	
	
	public  CreateModule (ModelBuild MBm)
	{
	 this.MB=MBm;	
	 this.model=MB.getModel();
	 this.owl=MB.getOWLModel();
     this.numEntity=MB.NumEntity;
     tempDir = MB.wd;
     ontName = MB.ontologyName;
     models=new ArrayList<OntModel>();
     clusters=new LinkedHashMap<Integer,Cluster>();
     modelNames=new ArrayList<String>();
	}
	
	public  CreateModule (ModelBuild MB, LinkedHashMap<Integer, Cluster> clusters)
	{
	 this.MB=MB;	
	 this.model=MB.getModel();
	 this.owl=MB.getOWLModel();
     this.numEntity=MB.NumEntity;
     tempDir = MB.wd;
     ontName = MB.ontologyName;
     models=new ArrayList<OntModel>();
     this.clusters=clusters;
     modelNames=new ArrayList<String>();
	}
	
	public ArrayList<OntModel> getOntModels()
	{
	    if(models==null)
	    	return createOWLFiles_Phase();
	    else
		return models;
	} 


///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////CreateOutput_Phase ////////////////////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//another implementation for owl file for each module

   public ArrayList<OntModel> createOWLFiles_Phase() //throws ConversionException
   {
	 if(MB==null)
	 { System.out.println("there is no model to get modules");
	     return null;}
	 if(clusters==null)
	 {
		 System.out.println("the model is not partitioned yet");
	 }
	 if(owl==null)
		 return createOntModelFiles();
        OWLOntology extractionSource = createSafeExtractionSource(MB != null ? MB.getOntoName() : null, owl);
        if (USE_MERGED_EXTRACTION_SOURCE) {
                extractionSource = buildExtractionSourceOntology(extractionSource.getOWLOntologyManager(), extractionSource);
        }
        OWLOntologyManager manager = extractionSource != null ? extractionSource.getOWLOntologyManager() : owl.getOWLOntologyManager();
        System.out.println("[OAPT-CreateModule] merge extraction source enabled=" + USE_MERGED_EXTRACTION_SOURCE);
	Set<OWLOntology> sourceClosure = owl.getImportsClosure();
	System.out.println("[OAPT-DIAG|SOURCE_CLOSURE] imports=" + owl.getImportsDeclarations().size()
			+ " closureOntologies=" + sourceClosure.size()
			+ " subClass=" + countAxiomsInClosure(sourceClosure, AxiomType.SUBCLASS_OF)
			+ " disjoint=" + countAxiomsInClosure(sourceClosure, AxiomType.DISJOINT_CLASSES)
			+ " equiv=" + countAxiomsInClosure(sourceClosure, AxiomType.EQUIVALENT_CLASSES)
			+ " domain=" + countAxiomsInClosure(sourceClosure, AxiomType.OBJECT_PROPERTY_DOMAIN)
			+ " range=" + countAxiomsInClosure(sourceClosure, AxiomType.OBJECT_PROPERTY_RANGE));
	Set<OWLOntology> effectiveClosure = extractionSource.getImportsClosure();
	System.out.println("[OAPT-DIAG|SOURCE_EFFECTIVE] imports=" + extractionSource.getImportsDeclarations().size()
			+ " closureOntologies=" + effectiveClosure.size()
			+ " subClass=" + countAxiomsInClosure(effectiveClosure, AxiomType.SUBCLASS_OF)
			+ " disjoint=" + countAxiomsInClosure(effectiveClosure, AxiomType.DISJOINT_CLASSES)
			+ " equiv=" + countAxiomsInClosure(effectiveClosure, AxiomType.EQUIVALENT_CLASSES)
			+ " domain=" + countAxiomsInClosure(effectiveClosure, AxiomType.OBJECT_PROPERTY_DOMAIN)
			+ " range=" + countAxiomsInClosure(effectiveClosure, AxiomType.OBJECT_PROPERTY_RANGE));
 	OWLOntologyManager managerN = null;
 	OWLOntology owlN = null;
 	OWLDataFactory factory = manager.getOWLDataFactory();
 	OWLDataFactory factoryN = null;
 	OWLClass thing = factory.getOWLThing();
	NodeList nList = MB.rbgmModel.getNamedClassNodes();
	ArrayList<ModuleSnapshot> moduleSnapshots = new ArrayList<ModuleSnapshot>();
	int i=0, count=0;
	for (Iterator<Cluster> j = clusters.values().iterator(); j.hasNext();)
	 {
		 Cluster cluster = j.next();
		 managerN = OWLManager.createOWLOntologyManager();
		 try {
			owlN = managerN.createOntology();
			factoryN = managerN.getOWLDataFactory();
		} catch (OWLOntologyCreationException e) {
			e.printStackTrace();
		}
		 OWLDeclarationAxiom axiomT = factoryN.getOWLDeclarationAxiom(thing);
		 AddAxiom adx = new AddAxiom(owlN, axiomT);
		 managerN.applyChange(adx);
		 Set<OWLClass> redClass = new HashSet<OWLClass>();
		 for (Iterator<Node> iter = cluster.listElements(); iter.hasNext();) {
	         Node inode = iter.next();
	         OntClass cls = model.getOntClass(inode.toString());
	         if(nList.contains(inode) && cls!=null)
	         {
	             IRI iri = IRI.create(cls.getURI());
	        	 OWLClass ocls = factory.getOWLClass(iri);
	        	 OWLDeclarationAxiom axiom = factory.getOWLDeclarationAxiom(ocls);
	        	 AddAxiom addAxiom = new AddAxiom(owlN, axiom);
	        	 managerN.applyChange(addAxiom);
                         Set<OWLClassAxiom> axioms = new HashSet<OWLClassAxiom>();
                         Set<OWLAxiom> referencingAxioms = new HashSet<OWLAxiom>();
                         try{
                         axioms = extractionSource.getAxioms(ocls);
                         referencingAxioms = extractionSource.getReferencingAxioms(ocls, Imports.EXCLUDED);
                         }
                         catch(ConversionException| IllegalStateException e){}
                         Iterator<OWLClassAxiom> it = axioms.iterator();
                         while(it.hasNext())
                         {
                                 OWLAxiom ax = it.next();
                                 owlN.addAxiom(ax);
                                 Iterator<OWLEntity> sg = ax.getSignature().iterator();
                                 while(sg.hasNext())
                                 {
                                         String name = sg.next().getIRI().getShortForm().toString();
                                        // if(cluster.getlistName().contains(name))
                                        //      axioms.remove(ax); //Samira:why remove?
                                 }
                         }
                         owlN.addAxioms(axioms);
                         owlN.addAxioms(referencingAxioms);
	        	 Iterator<OWLClassExpression> ssub=EntitySearcher.getSubClasses(ocls, extractionSource).iterator();
	        	 try{
	        	 while(ssub.hasNext())
	        	 {
	        		OWLClassExpression osubs=ssub.next();
	        		if(osubs.isOWLClass()){
	        		IRI iris=osubs.asOWLClass().getIRI();
	        		OWLClass osubc=factory.getOWLClass(iris);
	        		OWLDeclarationAxiom axiomSub = factory.getOWLDeclarationAxiom(osubc);
		        	AddAxiom addAxiomSub = new AddAxiom(owlN, axiomSub);
		        	managerN.applyChange(addAxiomSub);
	        		addAxiom=new AddAxiom(owlN,factory.getOWLSubClassOfAxiom(osubs, ocls));
	        		managerN.applyChange(addAxiom);
	        		Iterator<OWLAnnotationAssertionAxiom> axiomAn= EntitySearcher.getAnnotationAssertionAxioms((OWLEntity) osubs, extractionSource).iterator();
		          	 Set<OWLAnnotationAssertionAxiom> nAxio=new HashSet<OWLAnnotationAssertionAxiom>();
		          	while (axiomAn.hasNext()) {
		          	    nAxio.add(axiomAn.next());
		          	}
		          	 managerN.addAxioms(owlN, nAxio);
	        	 }}}
	        	 catch(IllegalStateException e){}
	        	 Iterator<OWLClassExpression> ssup=EntitySearcher.getSuperClasses(ocls, extractionSource).iterator();
	          	 Iterator<OWLAnnotationAssertionAxiom> axiomAn= EntitySearcher.getAnnotationAssertionAxioms(ocls, extractionSource).iterator();
	          	 Set<OWLAnnotationAssertionAxiom> nAxio=new HashSet<OWLAnnotationAssertionAxiom>();
	          	while (axiomAn.hasNext()) {
	          	    nAxio.add(axiomAn.next());
	          	}
	          	 managerN.addAxioms(owlN, nAxio);
	          	 addObjectPropDomain(extractionSource,factory,managerN,ocls,owlN);
	        	// addObjectPropRange(owl,managerN,ocls,owlN);
	        	 addDataPropDomain(extractionSource,factory,managerN,ocls,owlN);
	        	 //addDataPropRange(owl,managerN,ocls,owlN);
	        	 Iterator<OWLIndividual> cid=EntitySearcher.getIndividuals(ocls, extractionSource).iterator();//ocls.getIndividuals(owl).iterator();
	        	 while(cid.hasNext())
	        	 {
	        		 OWLIndividual inv=cid.next();
	        		 addAxiom= new AddAxiom(owlN, factory.getOWLClassAssertionAxiom(ocls, inv));
	        		 managerN.applyChange(addAxiom);
	        	 }
	        	 if(!(ssup==null))
	        	 {
	        		redClass.add(ocls);
	           	 }
	        if(EntitySearcher.getSuperClasses(ocls, owlN)==null) System.out.println(ocls.getIRI().toString());
	         }

	     }
		  /*OWLReasonerFactory reasonerFactory = new ElkReasonerFactory();
			OWLReasoner reasoner = reasonerFactory.createReasoner(owlN);
			reasoner.precomputeInferences(InferenceType.CLASS_HIERARCHY);*/
		 String moduleLabel = "Module_" + i;
		 owlN = applyLogicalAxiomFallback(cluster, extractionSource, owlN, moduleLabel);
		 owlN = maybeTightenTinyClusterModule(cluster, extractionSource, owlN, moduleLabel);
		 ModuleSnapshot moduleSnapshot = captureModuleSnapshot(i, cluster, owlN, moduleLabel);
		 logModuleExpansion(moduleSnapshot);
		 moduleSnapshots.add(moduleSnapshot);
		 String outPath = tempDir + ontName + "_Module_" + i + ".owl";
		 logModuleAxiomProfile("MODULE_IN_MEMORY", outPath, owlN);
		 saveOntology(owlN,outPath,moduleLabel);//"D:/result/test/"+ontName+"_Module_"+i+".owl"); //(owlN,outPath);
		  i++;
	 }
	 if (ENABLE_MODULE_OVERLAP_DIAGNOSTICS) {
		 logModuleOverlapDiagnostics(moduleSnapshots);
	 }
	 count=i;
	 //used during modules quality evaluation
	 numTree=new double[models.size()];
		for( i=0;i<models.size();i++)
		 {
			  List Trlist=new ArrayList();
			  OntModel mod=models.get(i);
			  OntClass thng = mod.getOntClass( OWL.Thing.getURI() );
			  Trlist=thng.listSubClasses(true).toList();
			  if(count>0) numTree[i]=Trlist.size();
		 }

	System.out.println("Modularization is done!!");
	Coordinator.FinishPartitioning = true;
	return models;
}

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
private static void addObjectPropDomain(OWLOntology ontology,OWLDataFactory factory, OWLOntologyManager manager,OWLClass ocls, OWLOntology ont)
{

	   for (OWLObjectPropertyDomainAxiom op : ontology.getAxioms(AxiomType.OBJECT_PROPERTY_DOMAIN)) {
         if (op.getDomain().equals(ocls)) {
             for(OWLObjectProperty oop : op.getObjectPropertiesInSignature())
             {
            	 OWLAxiom axio=factory.getOWLObjectPropertyDomainAxiom(oop, ocls);
            	 AddAxiom ax=new AddAxiom(ont,axio);
            	 manager.applyChange(ax);
            	 Set<OWLObjectPropertyRangeAxiom> axiomO=ontology.getObjectPropertyRangeAxioms(oop);
        		 manager.addAxioms(ont, axiomO);

            	 //Set<OWLObjectPropertyDomainAxiom> axiomO=ontology.getObjectPropertyDomainAxioms(oop);
            	 // manager.addAxioms(ont, axiomO);
            	  if(EntitySearcher.isFunctional(oop, ontology)){//oop.isFunctional(ontology)){
                 	 OWLFunctionalObjectPropertyAxiom axiom=factory.getOWLFunctionalObjectPropertyAxiom(oop);
                 	 AddAxiom addAxiom = new AddAxiom(ont, axiom);  manager.applyChange(addAxiom);
                  }

                  if(EntitySearcher.isInverseFunctional(oop, ontology)){//oop.isInverseFunctional(ontology)){
                 	 OWLInverseFunctionalObjectPropertyAxiom axiom=factory.getOWLInverseFunctionalObjectPropertyAxiom(oop);
                 	AddAxiom addAxiom = new AddAxiom(ont, axiom);  manager.applyChange(addAxiom);
                        }
                  if(EntitySearcher.isReflexive(oop, ontology)){//oop.isReflexive(ontology)){
                 	 OWLReflexiveObjectPropertyAxiom axiom=factory.getOWLReflexiveObjectPropertyAxiom(oop);
                 	AddAxiom addAxiom = new AddAxiom(ont, axiom);  manager.applyChange(addAxiom);
                  }
                  if(EntitySearcher.isIrreflexive(oop, ontology)){//oop.isIrreflexive(ontology)){
                 	 OWLIrreflexiveObjectPropertyAxiom axiom=factory.getOWLIrreflexiveObjectPropertyAxiom(oop);
                 	AddAxiom addAxiom = new AddAxiom(ont, axiom);  manager.applyChange(addAxiom);
                  }
                  if(EntitySearcher.isSymmetric(oop, ontology)){//oop.isSymmetric(ontology)){
                 	 OWLSymmetricObjectPropertyAxiom axiom=factory.getOWLSymmetricObjectPropertyAxiom(oop);
                 	AddAxiom addAxiom = new AddAxiom(ont, axiom);  manager.applyChange(addAxiom);
                  }
                  if(EntitySearcher.isTransitive(oop, ontology)){//oop.isTransitive(ontology)){
                 	 OWLTransitiveObjectPropertyAxiom axiom=factory.getOWLTransitiveObjectPropertyAxiom(oop);
                 	AddAxiom addAxiom = new AddAxiom(ont, axiom);  manager.applyChange(addAxiom);
                  }
                  Iterator<OWLObjectProperty>  sop=EntitySearcher.getSubProperties(oop, ontology).iterator();//oop.getSubProperties(ontology).iterator();
                  Iterator<OWLObjectPropertyExpression> eop=EntitySearcher.getEquivalentProperties(oop, ontology).iterator();//oop.getEquivalentProperties(ontology);
                  Set<OWLObjectPropertyExpression> eopN=new HashSet<OWLObjectPropertyExpression>();
                  while (eop.hasNext()) {
                	    eopN.add(eop.next());
                	}
                  Iterator<OWLObjectPropertyExpression>  iop=EntitySearcher.getInverses(oop, ontology).iterator();//oop.getInverses(ontology).iterator();
                  while(sop.hasNext())
                  {
                	  OWLObjectPropertyExpression sopi=sop.next();
                	  AddAxiom addAxiom = new AddAxiom(ont, factory.getOWLSubObjectPropertyOfAxiom(sopi, oop));
                	  manager.applyChange(addAxiom);
                  }
                  try{
                  while(iop.hasNext())
                  {
                	  OWLObjectPropertyExpression iopi=iop.next();
                	  AddAxiom addAxiom = new AddAxiom(ont, factory.getOWLInverseObjectPropertiesAxiom(oop, iopi));
                	  manager.applyChange(addAxiom);
                  }}
                  catch(IllegalStateException e){}
                  AddAxiom addAxiom = new AddAxiom(ont, factory.getOWLEquivalentObjectPropertiesAxiom(eopN));
                 manager.applyChange(addAxiom);

             }
          }
     }
}



////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
private static void addDataPropDomain(OWLOntology ontology, OWLDataFactory factory, OWLOntologyManager manager,OWLClass ocls,OWLOntology ont)
{
	 for (OWLDataPropertyDomainAxiom dp : ontology.getAxioms(AxiomType.DATA_PROPERTY_DOMAIN))
       {
	          if (dp.getDomain().equals(ocls)) {
	                for(OWLDataProperty odp : dp.getDataPropertiesInSignature())
	                {
	                	 OWLDataPropertyDomainAxiom axiomO=manager.getOWLDataFactory().getOWLDataPropertyDomainAxiom(odp, ocls);
	                	 AddAxiom ax=new AddAxiom(ont,axiomO);
	                	 manager.applyChange(ax);
	                	 //Set<OWLDataRange> sdr=odp.getRanges(ontology);
	                	 Set<OWLDataPropertyRangeAxiom> axiomDR=ontology.getDataPropertyRangeAxioms(odp);
	            		 manager.addAxioms(ont, axiomDR);
	            		 if(EntitySearcher.isFunctional(odp, ontology)){//odp.isFunctional(ontology)){
	                		 AddAxiom axio=new AddAxiom(ont,factory.getOWLFunctionalDataPropertyAxiom(odp));
	                		 manager.applyChange(axio);
	               	    }
	                	 Iterator<OWLDataPropertyExpression> edp=EntitySearcher.getEquivalentProperties(odp, ontology).iterator();//odp.getEquivalentProperties(ontology).iterator();
	                	 Iterator<OWLDataProperty> sdp=EntitySearcher.getSubProperties(odp, ontology).iterator();//odp.getSubProperties(ontology).iterator();
	                	 while(edp.hasNext())
	                	 {
	                		 OWLDataPropertyExpression idp=edp.next();
	                		 AddAxiom axio=new AddAxiom(ont, factory.getOWLSubDataPropertyOfAxiom(idp, odp));
	                		 manager.applyChange(axio);

	                	 }

	                	 while(sdp.hasNext())
	                	 {
	                		 OWLDataPropertyExpression idp=sdp.next();
	                		 AddAxiom axio=new AddAxiom(ont, factory.getOWLSubDataPropertyOfAxiom(idp, odp));
	                		  manager.applyChange(axio);
	                	 }
	                }

	            }
	       }
}

public void saveOntologyByName(String name , String loc)
{

     models.add(MB.getModel());
     numTree=new double[models.size()];
		for(int i=0;i<models.size();i++)
		 {
			  List Trlist=new ArrayList();
			  OntModel mod=models.get(i);
			  OntClass thng = mod.getOntClass( OWL.Thing.getURI() );
			  Trlist=thng.listSubClasses(true).toList();
			   numTree[i]=Trlist.size();
		 }
		OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
		 OWLDocumentFormat format=new RDFXMLDocumentFormat();
		 File file=new File(loc);
		 try {
			manager.saveOntology(MB.getOWLModel(), format, IRI.create(file.toURI()));
		} catch (OWLOntologyStorageException e) {
			e.printStackTrace();
		}
	System.out.println("Modularization is done!!");
	Coordinator.FinishPartitioning = true;

}

public void OntologySave(OWLOntology owlN, String loc)
{
	 OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
	 OWLDocumentFormat format=new RDFXMLDocumentFormat();
	 File file=new File(loc);
	 try {
		manager.saveOntology(owlN, format, IRI.create(file.toURI()));
	} catch (OWLOntologyStorageException e) {
		e.printStackTrace();
	}
	 OntDocumentManager mgr = new OntDocumentManager();
     mgr.setProcessImports(true);
     OntModelSpec spec = new OntModelSpec(OntModelSpec.OWL_MEM);
     Reasoner reasoner = ReasonerRegistry.getOWLReasoner();
     spec.setDocumentManager(mgr);
     OntModel model = ModelFactory.createOntologyModel(spec, null);
     model.read("file:"+loc);
     model.setStrictMode(false);
     models.add(model);
}

 private static void saveOntology(OWLOntology owlN, String loc)
 {
	 saveOntology(owlN, loc, "module");
 }

 private static void saveOntology(OWLOntology owlN, String loc, String moduleLabel)
 {
	 OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
	 OWLDocumentFormat format=new RDFXMLDocumentFormat();
	 File file=new File(loc);
	 try {
		manager.saveOntology(owlN, format, IRI.create(file.toURI()));
	} catch (OWLOntologyStorageException e) {
		e.printStackTrace();
	}
	 System.out.println("[OAPT-DIAG|MODULE_FILE] module=" + moduleLabel + " path=" + loc
			 + " exists=" + file.exists() + " bytes=" + (file.exists() ? file.length() : 0));
	 try {
		 OWLOntologyManager verifyManager = OWLManager.createOWLOntologyManager();
		 OWLOntology saved = verifyManager.loadOntologyFromOntologyDocument(file);
		 logModuleAxiomProfile("MODULE_RELOADED", moduleLabel, saved);
	 } catch (OWLOntologyCreationException e) {
		 System.out.println("[OAPT-DIAG|MODULE_RELOADED] module=" + moduleLabel + " error=" + e.getMessage());
	 }
	 OntDocumentManager mgr = new OntDocumentManager();
     mgr.setProcessImports(true);
     OntModelSpec spec = new OntModelSpec(OntModelSpec.OWL_MEM);
     Reasoner reasoner = ReasonerRegistry.getOWLReasoner();
     spec.setDocumentManager(mgr);
     OntModel model = ModelFactory.createOntologyModel(spec, null);
     try{
     model.read("file:"+loc);}
     catch(RiotException e){}
      model.setStrictMode(false);
     models.add(model);
 }

 private static void logModuleAxiomProfile(String marker, String moduleLabel, OWLOntology ontology) {
         if (ontology == null) {
                 System.out.println("[OAPT-DIAG|" + marker + "] module=" + moduleLabel + " ontology=null");
                 return;
         }
         System.out.println("[OAPT-DIAG|" + marker + "] module=" + moduleLabel
                        + " imports=" + ontology.getImportsDeclarations().size()
                        + " logicalAxioms=" + ontology.getLogicalAxiomCount()
                        + " classDecl=" + ontology.getAxiomCount(AxiomType.DECLARATION)
                        + " annotationAssertions=" + ontology.getAxiomCount(AxiomType.ANNOTATION_ASSERTION)
                        + " subClass=" + ontology.getAxiomCount(AxiomType.SUBCLASS_OF)
                        + " disjoint=" + ontology.getAxiomCount(AxiomType.DISJOINT_CLASSES)
                        + " equiv=" + ontology.getAxiomCount(AxiomType.EQUIVALENT_CLASSES)
                        + " domain=" + ontology.getAxiomCount(AxiomType.OBJECT_PROPERTY_DOMAIN)
                        + " range=" + ontology.getAxiomCount(AxiomType.OBJECT_PROPERTY_RANGE));
 }
 private static final class ModuleSnapshot {
         private final int moduleIndex;
         private final int clusterId;
         private final int clusterSize;
         private final String moduleLabel;
         private final int namedClassCount;
         private final int logicalAxiomCount;
         private final Set<String> classIris;
         private ModuleSnapshot(int moduleIndex, int clusterId, int clusterSize, String moduleLabel,
                         int namedClassCount, int logicalAxiomCount, Set<String> classIris) {
                 this.moduleIndex = moduleIndex;
                 this.clusterId = clusterId;
                 this.clusterSize = clusterSize;
                 this.moduleLabel = moduleLabel;
                 this.namedClassCount = namedClassCount;
                 this.logicalAxiomCount = logicalAxiomCount;
                 this.classIris = classIris;
         }
         private double getInflation() {
                 if (clusterSize <= 0) {
                         return 0.0d;
                 }
                 return namedClassCount / (double) clusterSize;
         }
 }
 private static final class ModuleOverlapStats {
         private final ModuleSnapshot left;
         private final ModuleSnapshot right;
         private final int intersectionSize;
         private final int unionSize;
         private final double jaccard;
         private final double containmentSmall;
         private final double containmentLarge;
         private ModuleOverlapStats(ModuleSnapshot left, ModuleSnapshot right, int intersectionSize, int unionSize,
                         double jaccard, double containmentSmall, double containmentLarge) {
                 this.left = left;
                 this.right = right;
                 this.intersectionSize = intersectionSize;
                 this.unionSize = unionSize;
                 this.jaccard = jaccard;
                 this.containmentSmall = containmentSmall;
                 this.containmentLarge = containmentLarge;
         }
         private boolean isNearDuplicate() {
                 return intersectionSize > 0
                                 && (jaccard >= NEAR_DUPLICATE_JACCARD
                                                 || containmentSmall >= NEAR_DUPLICATE_CONTAINMENT);
         }
 }
 private static ModuleSnapshot captureModuleSnapshot(int moduleIndex, Cluster cluster, OWLOntology ontology, String moduleLabel) {
         int clusterId = cluster != null ? cluster.getClusterID() : -1;
         int clusterSize = cluster != null ? cluster.getSize() : 0;
         Set<String> classIris = extractNamedClassIris(ontology);
         int logicalAxiomCount = ontology != null ? ontology.getLogicalAxiomCount() : 0;
         return new ModuleSnapshot(moduleIndex, clusterId, clusterSize, moduleLabel, classIris.size(),
                         logicalAxiomCount, classIris);
 }
 private static void logModuleExpansion(ModuleSnapshot snapshot) {
         if (snapshot == null) {
                 return;
         }
         System.out.println("[OAPT-DIAG|MODULE_EXPANSION] module=" + snapshot.moduleLabel
                         + " clusterId=" + snapshot.clusterId
                         + " clusterSize=" + snapshot.clusterSize
                         + " namedClasses=" + snapshot.namedClassCount
                         + " logicalAxioms=" + snapshot.logicalAxiomCount
                         + " inflation=" + formatDecimal(snapshot.getInflation()));
         if (snapshot.clusterSize > 0
                         && snapshot.clusterSize <= TINY_CLUSTER_MAX_SIZE
                         && snapshot.getInflation() >= TINY_CLUSTER_INFLATION_TRIGGER) {
                 System.out.println("[OAPT-WARN|TINY_CLUSTER_EXPANSION] module=" + snapshot.moduleLabel
                                 + " clusterId=" + snapshot.clusterId
                                 + " clusterSize=" + snapshot.clusterSize
                                 + " namedClasses=" + snapshot.namedClassCount
                                 + " logicalAxioms=" + snapshot.logicalAxiomCount
                                 + " inflation=" + formatDecimal(snapshot.getInflation())
                                 + " tighteningEnabled=" + ENABLE_TINY_CLUSTER_TIGHTENING);
         }
 }
 private static void logModuleOverlapDiagnostics(List<ModuleSnapshot> moduleSnapshots) {
         if (moduleSnapshots == null || moduleSnapshots.isEmpty()) {
                 return;
         }
         Map<String, Integer> classFrequency = new HashMap<String, Integer>();
         int totalMemberships = 0;
         for (ModuleSnapshot snapshot : moduleSnapshots) {
                 totalMemberships += snapshot.namedClassCount;
                 for (String iri : snapshot.classIris) {
                         Integer current = classFrequency.get(iri);
                         classFrequency.put(iri, current == null ? 1 : current + 1);
                 }
         }
         int comparedPairs = moduleSnapshots.size() > 1 ? (moduleSnapshots.size() * (moduleSnapshots.size() - 1)) / 2 : 0;
         int uniqueClasses = classFrequency.size();
         double avgModulesPerClass = uniqueClasses == 0 ? 0.0d : totalMemberships / (double) uniqueClasses;
         ArrayList<Map.Entry<String, Integer>> repeatedClasses = new ArrayList<Map.Entry<String, Integer>>(classFrequency.entrySet());
         repeatedClasses.sort(new Comparator<Map.Entry<String, Integer>>() {
                 public int compare(Map.Entry<String, Integer> left, Map.Entry<String, Integer> right) {
                         int byCount = Integer.compare(right.getValue(), left.getValue());
                         if (byCount != 0) {
                                 return byCount;
                         }
                         return left.getKey().compareTo(right.getKey());
                 }
         });
         ArrayList<ModuleOverlapStats> overlapPairs = new ArrayList<ModuleOverlapStats>();
         ModuleOverlapStats[] bestOverlapPerModule = new ModuleOverlapStats[moduleSnapshots.size()];
         int nearDuplicatePairs = 0;
         for (int leftIndex = 0; leftIndex < moduleSnapshots.size(); leftIndex++) {
                 for (int rightIndex = leftIndex + 1; rightIndex < moduleSnapshots.size(); rightIndex++) {
                         ModuleOverlapStats stats = computeModuleOverlap(moduleSnapshots.get(leftIndex), moduleSnapshots.get(rightIndex));
                         if (stats.intersectionSize <= 0) {
                                 continue;
                         }
                         overlapPairs.add(stats);
                         bestOverlapPerModule[leftIndex] = chooseBetterOverlap(bestOverlapPerModule[leftIndex], stats);
                         bestOverlapPerModule[rightIndex] = chooseBetterOverlap(bestOverlapPerModule[rightIndex], stats);
                         if (stats.isNearDuplicate()) {
                                 nearDuplicatePairs++;
                                 System.out.println("[OAPT-WARN|MODULE_NEAR_DUP] moduleA=" + stats.left.moduleLabel
                                                 + " moduleB=" + stats.right.moduleLabel
                                                 + " jaccard=" + formatDecimal(stats.jaccard)
                                                 + " containSmall=" + formatDecimal(stats.containmentSmall)
                                                 + " containLarge=" + formatDecimal(stats.containmentLarge)
                                                 + " intersection=" + stats.intersectionSize
                                                 + " sizes=" + stats.left.namedClassCount + "/" + stats.right.namedClassCount);
                         }
                 }
         }
         System.out.println("[OAPT-DIAG|MODULE_OVERLAP_SUMMARY] moduleCount=" + moduleSnapshots.size()
                         + " comparedPairs=" + comparedPairs
                         + " overlappingPairs=" + overlapPairs.size()
                         + " nearDuplicatePairs=" + nearDuplicatePairs
                         + " uniqueClasses=" + uniqueClasses
                         + " totalClassMemberships=" + totalMemberships
                         + " avgModulesPerClass=" + formatDecimal(avgModulesPerClass)
                         + " topRepeatedClasses=" + summarizeTopRepeatedClasses(repeatedClasses, 10));
         for (int i = 0; i < bestOverlapPerModule.length; i++) {
                 ModuleOverlapStats stats = bestOverlapPerModule[i];
                 if (stats == null) {
                         continue;
                 }
                 ModuleSnapshot owner = moduleSnapshots.get(i);
                 ModuleSnapshot peer = stats.left.moduleIndex == owner.moduleIndex ? stats.right : stats.left;
                 System.out.println("[OAPT-DIAG|MODULE_OVERLAP_MAX] module=" + owner.moduleLabel
                                 + " peer=" + peer.moduleLabel
                                 + " jaccard=" + formatDecimal(stats.jaccard)
                                 + " containSmall=" + formatDecimal(stats.containmentSmall)
                                 + " containLarge=" + formatDecimal(stats.containmentLarge)
                                 + " intersection=" + stats.intersectionSize
                                 + " union=" + stats.unionSize
                                 + " peerNamedClasses=" + peer.namedClassCount);
         }
         overlapPairs.sort(new Comparator<ModuleOverlapStats>() {
                 public int compare(ModuleOverlapStats left, ModuleOverlapStats right) {
                         int byJaccard = Double.compare(right.jaccard, left.jaccard);
                         if (byJaccard != 0) {
                                 return byJaccard;
                         }
                         int byContainment = Double.compare(right.containmentSmall, left.containmentSmall);
                         if (byContainment != 0) {
                                 return byContainment;
                         }
                         return Integer.compare(right.intersectionSize, left.intersectionSize);
                 }
         });
         int limit = Math.min(OVERLAP_TOP_PAIR_LIMIT, overlapPairs.size());
         for (int i = 0; i < limit; i++) {
                 ModuleOverlapStats stats = overlapPairs.get(i);
                 System.out.println("[OAPT-DIAG|MODULE_OVERLAP_TOP] rank=" + (i + 1)
                                 + " moduleA=" + stats.left.moduleLabel
                                 + " moduleB=" + stats.right.moduleLabel
                                 + " jaccard=" + formatDecimal(stats.jaccard)
                                 + " containSmall=" + formatDecimal(stats.containmentSmall)
                                 + " containLarge=" + formatDecimal(stats.containmentLarge)
                                 + " intersection=" + stats.intersectionSize
                                 + " union=" + stats.unionSize
                                 + " sizes=" + stats.left.namedClassCount + "/" + stats.right.namedClassCount);
         }
 }
 private static ModuleOverlapStats chooseBetterOverlap(ModuleOverlapStats current, ModuleOverlapStats candidate) {
         if (candidate == null) {
                 return current;
         }
         if (current == null) {
                 return candidate;
         }
         if (Double.compare(candidate.jaccard, current.jaccard) > 0) {
                 return candidate;
         }
         if (Double.compare(candidate.jaccard, current.jaccard) == 0
                         && Integer.compare(candidate.intersectionSize, current.intersectionSize) > 0) {
                 return candidate;
         }
         return current;
 }
 private static ModuleOverlapStats computeModuleOverlap(ModuleSnapshot left, ModuleSnapshot right) {
         if (left == null || right == null) {
                 return new ModuleOverlapStats(left, right, 0, 0, 0.0d, 0.0d, 0.0d);
         }
         Set<String> smaller = left.classIris.size() <= right.classIris.size() ? left.classIris : right.classIris;
         Set<String> larger = smaller == left.classIris ? right.classIris : left.classIris;
         int intersectionSize = 0;
         for (String iri : smaller) {
                 if (larger.contains(iri)) {
                         intersectionSize++;
                 }
         }
         int unionSize = left.classIris.size() + right.classIris.size() - intersectionSize;
         int smallSize = Math.min(left.classIris.size(), right.classIris.size());
         int largeSize = Math.max(left.classIris.size(), right.classIris.size());
         double jaccard = unionSize == 0 ? 0.0d : intersectionSize / (double) unionSize;
         double containmentSmall = smallSize == 0 ? 0.0d : intersectionSize / (double) smallSize;
         double containmentLarge = largeSize == 0 ? 0.0d : intersectionSize / (double) largeSize;
         return new ModuleOverlapStats(left, right, intersectionSize, unionSize, jaccard, containmentSmall, containmentLarge);
 }
 private static String summarizeTopRepeatedClasses(List<Map.Entry<String, Integer>> repeatedClasses, int limit) {
         if (repeatedClasses == null || repeatedClasses.isEmpty() || limit <= 0) {
                 return "[]";
         }
         StringBuilder sb = new StringBuilder("[");
         int count = 0;
         for (Map.Entry<String, Integer> entry : repeatedClasses) {
                 if (entry.getValue() == null || entry.getValue().intValue() <= 1) {
                         break;
                 }
                 if (count > 0) {
                         sb.append(", ");
                 }
                 sb.append(entry.getValue()).append(':').append(entry.getKey());
                 count++;
                 if (count >= limit) {
                         break;
                 }
         }
         if (count == 0) {
                 return "[]";
         }
         sb.append(']');
         return sb.toString();
 }
 private static Set<String> extractNamedClassIris(OWLOntology ontology) {
         Set<String> classIris = new HashSet<String>();
         if (ontology == null) {
                 return classIris;
         }
         for (OWLClass owlClass : ontology.getClassesInSignature(Imports.EXCLUDED)) {
                 if (owlClass.getIRI() != null) {
                         classIris.add(owlClass.getIRI().toString());
                 }
         }
         return classIris;
 }
 private static OWLOntology maybeTightenTinyClusterModule(Cluster cluster, OWLOntology extractionSource,
                 OWLOntology candidateOntology, String moduleLabel) {
         if (candidateOntology == null || cluster == null) {
                 return candidateOntology;
         }
         int clusterSize = cluster.getSize();
         if (clusterSize <= 0 || clusterSize > TINY_CLUSTER_MAX_SIZE) {
                 return candidateOntology;
         }
         int candidateNamedClasses = candidateOntology.getClassesInSignature(Imports.EXCLUDED).size();
         double inflation = clusterSize == 0 ? 0.0d : candidateNamedClasses / (double) clusterSize;
         if (inflation < TINY_CLUSTER_INFLATION_TRIGGER) {
                 return candidateOntology;
         }
         if (!ENABLE_TINY_CLUSTER_TIGHTENING || extractionSource == null) {
                 return candidateOntology;
         }
         Set<OWLEntity> signature = buildModuleSignature(cluster, extractionSource);
         if (signature.isEmpty()) {
                 System.out.println("[OAPT-DIAG|MODULE_TIGHTEN] module=" + moduleLabel + " skipped=empty_signature");
                 return candidateOntology;
         }
         try {
                 OWLOntology tightened = ModuleExtractor.extractModule(signature, extractionSource,
                                 "http://oapt.local/module-tight/" + moduleLabel, ModuleType.BOT);
                 int tightenedNamedClasses = tightened.getClassesInSignature(Imports.EXCLUDED).size();
                 double reduction = candidateNamedClasses == 0 ? 0.0d
                                 : (candidateNamedClasses - tightenedNamedClasses) / (double) candidateNamedClasses;
                 boolean keepsSignature = containsSignatureClasses(tightened, signature);
                 System.out.println("[OAPT-DIAG|MODULE_TIGHTEN] module=" + moduleLabel
                                 + " mode=BOT"
                                 + " clusterSize=" + clusterSize
                                 + " candidateNamedClasses=" + candidateNamedClasses
                                 + " tightenedNamedClasses=" + tightenedNamedClasses
                                 + " candidateLogicalAxioms=" + candidateOntology.getLogicalAxiomCount()
                                 + " tightenedLogicalAxioms=" + tightened.getLogicalAxiomCount()
                                 + " reduction=" + formatDecimal(reduction)
                                 + " keepsSignature=" + keepsSignature);
                 if (keepsSignature
                                 && tightened.getLogicalAxiomCount() > 0
                                 && tightenedNamedClasses < candidateNamedClasses
                                 && reduction >= TINY_CLUSTER_MIN_REDUCTION) {
                         return tightened;
                 }
         } catch (OWLOntologyCreationException e) {
                 System.out.println("[OAPT-DIAG|MODULE_TIGHTEN] module=" + moduleLabel + " error=" + e.getMessage());
         }
         return candidateOntology;
 }
 private static boolean containsSignatureClasses(OWLOntology ontology, Set<OWLEntity> signature) {
         Set<String> classIris = extractNamedClassIris(ontology);
         for (OWLEntity entity : signature) {
                 if (entity != null && entity.isOWLClass() && !classIris.contains(entity.getIRI().toString())) {
                         return false;
                 }
         }
         return true;
 }
 private static String formatDecimal(double value) {
         return String.format(Locale.ROOT, "%.4f", value);
 }
 private static OWLOntology applyLogicalAxiomFallback(Cluster cluster, OWLOntology extractionSource,
                 OWLOntology candidateOntology, String moduleLabel) {
         if (candidateOntology == null || candidateOntology.getLogicalAxiomCount() > 0) {
                 return candidateOntology;
         }
         if (cluster == null || extractionSource == null) {
                 return candidateOntology;
         }
         Set<OWLEntity> signature = buildModuleSignature(cluster, extractionSource);
         System.out.println("[OAPT-DIAG|MODULE_FALLBACK] module=" + moduleLabel
                         + " trigger=zero_logical_axioms"
                         + " signatureSize=" + signature.size()
                         + " candidateAxioms=" + candidateOntology.getAxiomCount());
         if (signature.isEmpty()) {
                 System.out.println("[OAPT-DIAG|MODULE_FALLBACK] module=" + moduleLabel + " skipped=empty_signature");
                 return candidateOntology;
         }
         try {
                 OWLOntology extracted = ModuleExtractor.extractModule(signature, extractionSource,
                                 "http://oapt.local/module/" + moduleLabel, ModuleType.STAR);
                 System.out.println("[OAPT-DIAG|MODULE_FALLBACK] module=" + moduleLabel
                                 + " extractedAxioms=" + extracted.getAxiomCount()
                                 + " logicalAxioms=" + extracted.getLogicalAxiomCount()
                                 + " subClass=" + extracted.getAxiomCount(AxiomType.SUBCLASS_OF)
                                 + " equiv=" + extracted.getAxiomCount(AxiomType.EQUIVALENT_CLASSES)
                                 + " domain=" + extracted.getAxiomCount(AxiomType.OBJECT_PROPERTY_DOMAIN)
                                 + " range=" + extracted.getAxiomCount(AxiomType.OBJECT_PROPERTY_RANGE));
                 if (extracted.getLogicalAxiomCount() > 0 || extracted.getAxiomCount() > candidateOntology.getAxiomCount()) {
                         return extracted;
                 }
         } catch (OWLOntologyCreationException e) {
                 System.out.println("[OAPT-DIAG|MODULE_FALLBACK] module=" + moduleLabel + " error=" + e.getMessage());
         }
         return candidateOntology;
 }
 private static Set<OWLEntity> buildModuleSignature(Cluster cluster, OWLOntology extractionSource) {
         Set<OWLEntity> signature = new HashSet<OWLEntity>();
         if (cluster == null || extractionSource == null) {
                 return signature;
         }
         OWLDataFactory dataFactory = extractionSource.getOWLOntologyManager().getOWLDataFactory();
         for (String uri : cluster.getURI()) {
                 if (uri == null || uri.trim().isEmpty()) {
                         continue;
                 }
                 try {
                         signature.add(dataFactory.getOWLClass(IRI.create(uri)));
                 } catch (RuntimeException e) {
                         System.out.println("[OAPT-DIAG|MODULE_FALLBACK] invalid_signature_uri=" + uri + " error=" + e.getMessage());
                 }
         }
         return signature;
 }
 private static boolean readBooleanFlag(String systemPropertyName, String envVarName, boolean defaultValue) {
		 String value = System.getProperty(systemPropertyName);
		 if (value == null || value.trim().isEmpty()) {
				 value = System.getenv(envVarName);
		 }
		 if (value == null || value.trim().isEmpty()) {
				 return defaultValue;
		 }
		 return Boolean.parseBoolean(value.trim());
 }

 private static int readIntFlag(String systemPropertyName, String envVarName, int defaultValue) {
		 String value = System.getProperty(systemPropertyName);
		 if (value == null || value.trim().isEmpty()) {
				 value = System.getenv(envVarName);
		 }
		 if (value == null || value.trim().isEmpty()) {
				 return defaultValue;
		 }
		 try {
				 return Integer.parseInt(value.trim());
		 } catch (NumberFormatException e) {
				 return defaultValue;
		 }
 }

 private static double readDoubleFlag(String systemPropertyName, String envVarName, double defaultValue) {
		 String value = System.getProperty(systemPropertyName);
		 if (value == null || value.trim().isEmpty()) {
				 value = System.getenv(envVarName);
		 }
		 if (value == null || value.trim().isEmpty()) {
				 return defaultValue;
		 }
		 try {
				 return Double.parseDouble(value.trim());
		 } catch (NumberFormatException e) {
				 return defaultValue;
		 }
 }

 private static int countAxiomsInClosure(Set<OWLOntology> closure, AxiomType<?> axiomType) {
	 int count = 0;
	 for (OWLOntology ontology : closure) {
		 count += ontology.getAxiomCount(axiomType);
	 }
	 return count;
 }
 private static OWLOntology createSafeExtractionSource(String ontologyPath, OWLOntology fallbackOntology) {
         if (ontologyPath == null || ontologyPath.trim().isEmpty()) {
                 return fallbackOntology;
         }
         try (InputStream in = openOntologyStream(ontologyPath)) {
                 OWLOntologyManager safeManager = OWLManager.createOWLOntologyManager();
                 OWLOntologyLoaderConfiguration config = new OWLOntologyLoaderConfiguration()
                                 .setMissingImportHandlingStrategy(MissingImportHandlingStrategy.SILENT);
                 OWLOntology loaded = safeManager.loadOntologyFromOntologyDocument(new StreamDocumentSource(in), config);
                 OWLOntology copy = safeManager.createOntology();
                 safeManager.addAxioms(copy, loaded.getAxioms(Imports.EXCLUDED));
                 for (OWLAnnotation annotation : loaded.getAnnotations()) {
                         safeManager.applyChange(new AddOntologyAnnotation(copy, annotation));
                 }
                 System.out.println("[OAPT-DIAG|SOURCE_SAFE] path=" + ontologyPath
                                 + " axiomCount=" + copy.getAxiomCount()
                                 + " logicalAxioms=" + copy.getLogicalAxiomCount()
                                 + " subClass=" + copy.getAxiomCount(AxiomType.SUBCLASS_OF)
                                 + " equiv=" + copy.getAxiomCount(AxiomType.EQUIVALENT_CLASSES)
                                 + " domain=" + copy.getAxiomCount(AxiomType.OBJECT_PROPERTY_DOMAIN)
                                 + " range=" + copy.getAxiomCount(AxiomType.OBJECT_PROPERTY_RANGE));
                 return copy;
         } catch (Exception e) {
                 System.out.println("[OAPT-DIAG|SOURCE_SAFE] fallback=true path=" + ontologyPath + " error=" + e.getMessage());
                 return fallbackOntology;
         }
 }
 private static InputStream openOntologyStream(String ontologyPath) throws IOException {
         if (ontologyPath.endsWith(".gz")) {
                 return new GZIPInputStream(new FileInputStream(ontologyPath));
         }
         return new FileInputStream(ontologyPath);
 }
 private static OWLOntology buildExtractionSourceOntology(OWLOntologyManager manager, OWLOntology baseOntology) {
	 Set<OWLOntology> loadedOntologies = manager.getOntologies();
	 if (loadedOntologies == null || loadedOntologies.size() <= 1) {
		 return baseOntology;
	 }
	 try {
		 OWLOntologyManager mergedManager = OWLManager.createOWLOntologyManager();
		 OWLOntology merged = mergedManager.createOntology();
		 for (OWLOntology ontology : loadedOntologies) {
			 mergedManager.addAxioms(merged, ontology.getAxioms());
		 }
		 System.out.println("[OAPT-DIAG|SOURCE_MERGED] ontologies=" + loadedOntologies.size()
				 + " axioms=" + merged.getAxiomCount());
		 return merged;
	 } catch (OWLOntologyCreationException e) {
		 System.out.println("[OAPT-DIAG|SOURCE_MERGED] failed=" + e.getMessage());
		 return baseOntology;
	 }
 }
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
private  void createLink_Phase()
{
	clusters = Coordinator.clusters;
	for (Iterator<Cluster> i = clusters.values().iterator(); i.hasNext();) {
		Cluster icluster = i.next();  
		//System.out.println("Cluster:\t"+i);icluster.printCluster();
		addProperties(icluster); 
		//System.out.println(icluster.getClusterID()+"\t"+icluster.getElements().size()); 
		//icluster.printCluster();
	}
}

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
private void addProperties(Cluster icluster)
{
	Iterator<Node> stm= MB.rbgmModel.listStmtNodes();
	boolean isDatatype = false;
	Cluster tempCluster = new Cluster(0);
	while (stm.hasNext()){
		Node istm= stm.next();
		Node iobject = istm.getObject();
		Node isubject = istm.getSubject();
		Node ipredicate = istm.getPredicate();
		if ((ipredicate.getLocalName() != null) && (ipredicate.getLocalName().toLowerCase().toString().equals("domain") || ipredicate.getLocalName().toLowerCase().toString().equals("range")))
		{
			/*	isDatatype = false;
			ExtendedIterator datalist= BuildModel.OntModel.listDatatypeProperties(); 
			while (datalist.hasNext()){
			Object id= datalist.next();
			if (id.toString() == ipredicate.toString() || id.toString() ==isubject.toString() ){
			isDatatype = true;
				}
			}
			if (isDatatype == false){*/
		int u= clusterExistence(iobject, isubject,  icluster);
		if (u == 1){
			//icluster.putElement(isubject.toString(), isubject);
			tempCluster.putElement(isubject.toString(), isubject);
		}else if (u == 2){
			//icluster.putElement(iobject.toString(), iobject);
			tempCluster.putElement(iobject.toString(), iobject);
		}
		//}
		}
	}
	Iterator<Node> ilist =tempCluster.listElements();
	while (ilist.hasNext()){
		Node ind = ilist.next();
		icluster.putElement(ind.toString(), ind);
	}
}
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
private static int clusterExistence (Node inode, Node jnode , Cluster icluster)
{
	int u=0;

	Iterator<Node> ls= icluster.listElements();
	while (ls.hasNext()){
		Node nd = ls.next();
		if (nd.equals(inode) ){
			u=1;
		}else if (nd.equals(jnode) ){
			u=2;
		}
	}
	return u;
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
 //another implmentation of create output
  public   ArrayList<OntModel> createOntModelFiles()
   {
	 //clusters= Coordinator.clusters;
	 int KNumCH=clusters.size();
	 NumLickConcept = new int [KNumCH][numEntity+1]; // This array store the number of link for each element in each cluster
     ArrayList<Cluster> list = new ArrayList<Cluster>();
     for (Iterator<Cluster> i = clusters.values().iterator(); i.hasNext();) 
     {
      list.add(i.next());
     }
    LinkedHashMap<String, Integer> uriToClusterID = new LinkedHashMap<String, Integer>();
    for (int i = 0, n = list.size(); i < n; i++) {
     Cluster cluster = list.get(i);
     int clusterID = cluster.getClusterID();
     for (Iterator<Node> iter = cluster.listElements(); iter.hasNext();) {
         Node inode= iter.next();
    	 String uri = inode.toString(); 
         uriToClusterID.put(uri, clusterID);
     }
    }
 
    RDFSentenceGraph sg = new RDFSentenceGraph(MB.rbgmModel.getOntModel());
    sg.build(); //build with list statement of original ontology model
    ArrayList <String> iii= sg.getOntologyURIs();
    sg.filter(new OntologyHeaderFilter(sg.getOntologyURIs()));
    sg.filter(new PureSchemaFilter());
   
    //Creating one model for each partition to store them as separated files
    models = new ArrayList<OntModel>(list.size()); // create models (Array list with OntModel type with number of partition (NumCH))
    LinkedHashMap<Integer, Integer> clusterIDToOntModelID = new LinkedHashMap<Integer, Integer>();
    for (int i = 0, n = list.size(); i < n; i++) 
    {
     models.add(ModelFactory.createOntologyModel()); //Create as RDF format
     int cid = list.get(i).getClusterID();
     clusterIDToOntModelID.put(cid, i);
    }
    for (int i = 0, n = sg.getRDFSentences().size(); i < n; i++)
    {
     RDFSentence sentence = sg.getRDFSentence(i);     
     ArrayList<String> uris = sentence.getSubjectDomainVocabularyURIs(); 
     LinkedHashMap<Integer, Object> uniqueURIs = new LinkedHashMap<Integer, Object>();
     for (int j = 0, m = uris.size(); j < m; j++) {
         Integer clusterID = uriToClusterID.get(uris.get(j));
         if (clusterID != null) {
             uniqueURIs.put(clusterID, null);
         }
        }
      if (uniqueURIs.size() == 1) {
         Integer cid = uniqueURIs.keySet().iterator().next();
         Integer mid = clusterIDToOntModelID.get(cid);
         OntModel block = models.get(mid); //mid is the cluster index
         ArrayList<Statement> statements = sentence.getStatements();
         
         for (int j = 0, m = statements.size(); j < m; j++) {
        	 block.add(statements.get(j));  
        	 // if one statement add to the file, we should for its subject-object save the number of  link
        	 RDFNode ObjectURI = statements.get(j).getObject();
             RDFNode SubjectURI = statements.get(j).getSubject();
             RDFNode PropertyURI = statements.get(j).getPredicate();  
             if (ObjectURI.isURIResource() && SubjectURI.isURIResource() ){
	             String[] iProperty = PropertyURI.toString().split("\\#");
	       		 String[] iSubject = SubjectURI.toString().split("\\#");
	       		 String[] iObject = ObjectURI.toString().split("\\#");
	       		 if(iProperty!=null && iSubject!=null && iObject!=null)
	       		 {
	       		 if (iProperty.length>1){
		       		 if (iProperty[1].toLowerCase().equals("subclassof") || iProperty[1].toLowerCase().equals("haspropoerty")) { // TO DO: we should those acceptable property in this line such as SubclassOf 
			         	 int indexSubjectName =0;
			         	 if(iSubject.length >1) indexSubjectName=MB.findIndex(iSubject[1]); 
				         if (indexSubjectName >0 )
				             {NumLickConcept[mid][indexSubjectName] = NumLickConcept[mid][indexSubjectName] +1; }  // mid is the index of CH
				      	 int indexObjectName =0;
				      	 if(iObject.length>1) MB.findIndex(iObject[1]); 
				      	 if (indexObjectName >0 )
				         	 {NumLickConcept[mid][indexObjectName] = NumLickConcept[mid][indexObjectName] +1; }
			          }
	       		 	}
	       		 }
	       	}
         }
     }
 }
 


 
 // adding root 1- for Root concept (RootTag=false) ,  2- for those element with numLink=1
 	//First phase (1-for Root concept (RootTag=false))
	//if the node does not have superNode, we suppose it is Root and it is alone, so we call addRoot() function for it
 	numAloneElemnt = new int [KNumCH];
 	for (int ia=0; ia<MB.NumEntity; ia++){
		 if (MB.entities.get(ia).getNamedSupers() == null){
			 Node alone_element= MB.entities.get(ia); 
			 int indexCH_aloneElement = uriToClusterID.get(MB.entities.get(ia).toString());
			 addRoot(alone_element.toString(),indexCH_aloneElement ); //add this element in the ch block
			 numAloneElemnt [indexCH_aloneElement] = numAloneElemnt [indexCH_aloneElement] +1; 
			 //since we add one link in the file (alone_elemenet, subClassOf, "Thing"), so, we should count one link for alone_element in the NumLickConcept array 
			 NumLickConcept[indexCH_aloneElement][ia] = NumLickConcept[indexCH_aloneElement][ia] +2; //in the next lines, if this array home==1, then it thinks it is alone and does not link to Thing class, so, we add (+2) till it does not be equal 1
			 // we count those classes that are connected to alone_element
			 Iterator<Node> listStm = MB.rbgmModel.listStmtNodes();
			 while (listStm.hasNext()){
				 Node st= listStm.next();
				if (st.getPredicate().getLocalName().toLowerCase().equals("subclassof") ){
				 if (st.getSubject().getLocalName() != null && st.getObject().getLocalName() != null){
					 if (st.getSubject() == alone_element){
						 int isx= MB.findIndex(st.getObject().getLocalName());
						 if ((isx>0) && (uriToClusterID.get(st.getObject().toString()) != null) )  NumLickConcept[indexCH_aloneElement][isx] = NumLickConcept[indexCH_aloneElement][isx] +2;
					 }
					 if (st.getObject() == alone_element){
						 int isx= MB.findIndex(st.getSubject().getLocalName());
						 if ((isx>0) && (uriToClusterID.get(st.getSubject().toString()) != null) )  NumLickConcept[indexCH_aloneElement][isx] = NumLickConcept[indexCH_aloneElement][isx] +2;
					 }
				 }
				}
			 }
		}
	}
 
	//Second phase (2- for those element with numLink=1)		
	for (int i=0; i<KNumCH; i++){
		for (int j=0; j<MB.NumEntity; j++){
			if (NumLickConcept[i][j] == 1) {
				//addRoot(BuildModel.entities.get(j).toString(), i);
				numAloneElemnt [i] = numAloneElemnt [i] +1;
				// add it in NumLinkConcept till do not add twice one statements to Thing
				 // we count those classes that are connected to alone_element
				 Iterator<Node> listStm = MB.rbgmModel.listStmtNodes();
				 while (listStm.hasNext()){
					 Node st= listStm.next();
					if (st.getPredicate().getLocalName().toLowerCase().equals("subclassof") ){
					 if (st.getSubject().getLocalName() != null && st.getObject().getLocalName() != null){
						 if (st.getSubject() == MB.entities.get(j)){
							 int isx= MB.findIndex(st.getObject().getLocalName());
							 if ((isx>0) && (uriToClusterID.get(st.getObject().toString()) != null))  NumLickConcept[i][isx] = NumLickConcept[i][isx] +2;
						 }
						 if (st.getObject() == MB.entities.get(j)){
							 int isx= MB.findIndex(st.getSubject().getLocalName());
							 if ((isx>0) && (uriToClusterID.get(st.getSubject().toString()) != null) )  NumLickConcept[i][isx] = NumLickConcept[i][isx] +2;
						 }
					 }
					}
				 }
			}
		}
	}
 
	numTree=new double[models.size()];
	for(int i=0;i<models.size();i++)
	 {
		  List Trlist=new ArrayList();
		  OntModel model=models.get(i);
		  OntClass thing = model.getOntClass( OWL.Thing.getURI() );
		  Trlist=thing.listSubClasses(true).toList();
		  if(list!=null) numTree[i]=Trlist.size(); 
	 }
	
 
 //Creating Files in Temp folder
 for (int i = 0, n = models.size(); i < n; i++) {
     int cid = list.get(i).getClusterID();
     String filepath = tempDir + ontName + "_module_" + cid + ".owl";
     File file = new File(filepath);
     if (file.exists()) {
         file.delete();
     }
     Cluster c=list.get(cid);
     
     OntModel block = models.get(i); // Write one block as one model in owl file
      try {
         FileOutputStream fos = new FileOutputStream(filepath);
         BufferedOutputStream bos = new BufferedOutputStream(fos);
         block.write(bos, "RDF/XML"); //XML format
         //block.write(bos, "Turtle"); //compact and more readable
         bos.close();
         fos.close();
     } catch (IOException e) {
         e.printStackTrace();
     }
     block.close();
   }
  return models;
  }


///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//another implementation for creating output using OWL API
  public   ArrayList<OntModel> createOutput_Phase3()
  {
	clusters = Coordinator.clusters;
	NumLickConcept = new int [Coordinator.KNumCH][numEntity+1]; // This array store the number of link for each element in each cluster
	ArrayList<Cluster> list = new ArrayList<Cluster>();
	 for (Iterator<Cluster> i = clusters.values().iterator(); i.hasNext();) {
	     list.add(i.next());
	 }
	//>>>start to creating a list of OWLmodels
	 models = new ArrayList<OntModel>(list.size()); // create one array of OWLmodels 
	 for (int i = 0, n = list.size(); i < n; i++) { 
		models.add(ModelFactory.createOntologyModel());
	 } 
	 //>>>> finish creating a list of OWLmodels
	 
	 
	 //>> Saving which nodes exist in which cluster(module), e.g "Paper" node exist in cluster 1 since its clusterID is 1
	 for (int i = 0, n = list.size(); i < n; i++) {
	     Cluster cluster = list.get(i);
	     int clusterID = cluster.getClusterID();
	     for (Iterator<Node> iter = cluster.listElements(); iter.hasNext();) {
	         Node inode= iter.next();
	    	 String uri = inode.toString(); 
	         uriToClusterID.put(uri, clusterID);
	     }
	 }
	 //>> Finishing the saving index of cluster's node
	 
	 
	 //>>>> Start to process all statements of original model, then put each statements in proper modules
	// for (int i = 0, n = Controller.KNumCH; i < n; i++) 
	 {
		StmtIterator stm= MB.getModel().listStatements(); 	
		while (stm.hasNext()){
			Statement istm= stm.nextStatement();
			Resource isubject = istm.getSubject();
			RDFNode iobject = istm.getObject();
			Property ipredicate = istm.getPredicate();
			if (isubject.getLocalName() != null) // we do not add those statements that contain a "Blank nodes"
			{
				Integer clusterID = uriToClusterID.get(isubject.toString());
				if (clusterID != null){
					models.get(clusterID).add(istm);
					countLink(istm, clusterID);
				}
			}else if (iobject != null){
				Integer clusterID = uriToClusterID.get(iobject.toString());
				if (clusterID != null){
					models.get(clusterID).add(istm);
					countLink(istm, clusterID);
				}
			} else if (ipredicate.getLocalName() != null){  // we do not add those statements that contain a "Blank nodes"
				Integer clusterID = uriToClusterID.get(ipredicate.toString());
				if (clusterID != null){
					models.get(clusterID).add(istm);
					countLink(istm, clusterID);
				}
			}
	}
	 }
	//>>>> Finish processing statements
	  processAloneElments();
	
	//>>save our generated modules as files in temp folder
	 for (int i = 0, n = models.size(); i < n; i++) {
	     int cid = list.get(i).getClusterID();
	     String filepath = tempDir + ontName + "_Module_" + cid + ".owl";
	     File file = new File(filepath);
	     if (file.exists()) {
	         file.delete();
	     }	     
	     OntModel block = models.get(i); // Write one block as one model in owl file
	     OWLOntology owll=((OWLOntology) block);
	     saveOntology(owll,filepath);
	      try {
	         FileOutputStream fos = new FileOutputStream(filepath);//create on the local address
	         BufferedOutputStream bos = new BufferedOutputStream(fos);
	         try{
	        // Model m=block.write(bos, "RDF/XML"); //XML format  
	         }
	         catch(BadURIException e){
	        	 block.write(bos,"TURTLE");   
	         }
	         bos.close();
	         fos.close();
	     } catch (IOException e) {
	         e.printStackTrace();
	     }
	     //block.close(); //TO DO: it should not comment (but if it works, we reach to error in AddRoot function (ClosedException: already closed))
	 }
	//>>finishing saving
	
		
	//Save values for Evaluating panel
	numTree=new double[models.size()];
	for(int i=0;i<models.size();i++)
	 {
		  List Trlist=new ArrayList();
		  OntModel model=models.get(i);
		  OntClass thing = model.getOntClass( OWL.Thing.getURI() );
		  Trlist=thing.listSubClasses(true).toList();
		  if(list!=null) numTree[i]=Trlist.size(); 
	 }
 
 
	 
	return models; 

}
/////////////////////////////////////////////////////////////////////////////////////////////////
private void countLink(Statement statements, Integer clusterID){
	 // if one statement add to the file, we should for its subject-object save the number of  link
	 RDFNode ObjectURI = statements.getObject();
    RDFNode SubjectURI = statements.getSubject();
    RDFNode PropertyURI = statements.getPredicate();  
    if (ObjectURI.isURIResource() && SubjectURI.isURIResource() ){
        String[] iProperty = PropertyURI.toString().split("\\#");
  		 String[] iSubject = SubjectURI.toString().split("\\#");
  		 String[] iObject = ObjectURI.toString().split("\\#");
  		 if(iProperty!=null && iSubject!=null && iObject!=null)
  		 {
  		 if (iProperty.length>1){
      		 if (iProperty[1].toLowerCase().equals("subclassof") || iProperty[1].toLowerCase().equals("haspropoerty")) { // TO DO: we should those acceptable property in this line such as SubclassOf 
	         	 int indexSubjectName =0;
	         	 if(iSubject.length >1) indexSubjectName=MB.findIndex(iSubject[1]); 
		         if (indexSubjectName >0 )
		             {NumLickConcept[clusterID][indexSubjectName] = NumLickConcept[clusterID][indexSubjectName] +1; }  // mid is the index of CH
		      	 int indexObjectName =0;
		      	 if(iObject.length>1) MB.findIndex(iObject[1]); 
		      	 if (indexObjectName >0 )
		         	 {NumLickConcept[clusterID][indexObjectName] = NumLickConcept[clusterID][indexObjectName] +1; }
	          }
  		 	}
  		 }
  	}
    
}
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
private void  processAloneElments(){
	 // adding root 1- for Root concept (RootTag=false) ,  2- for those element with numLink=1
	//First phase (1-for Root concept (RootTag=false))
	//if the node does not have superNode, we suppose it is Root and it is alone, so we call addRoot() function for it
	numAloneElemnt = new int [Coordinator.KNumCH]; //delete
	for (int ia=0; ia<MB.NumEntity; ia++){ 
		Node alone_element= MB.entities.get(ia);
		if(alone_element!=null)
		{
		//System.out.println(uriToClusterID.size());
		Integer indexCH_aloneElement = uriToClusterID.get(alone_element.toString());
		if(indexCH_aloneElement!=null){
		NodeList supAloneElem= MB.entities.get(ia).getNamedSupers();
		if (supAloneElem == null){
			ConnectAloneElement (alone_element,indexCH_aloneElement, ia);
		}
		else{ //Maybe one concept has superNode but its superNode exist in another cluster, in this case, this concept is alone in VS
			boolean test = false;
			for (int s=0; s<supAloneElem.size();s++){
				test =ExistinClusterTest(supAloneElem.get(s),indexCH_aloneElement);
			}
			if (test == false){
				ConnectAloneElement (alone_element,indexCH_aloneElement, ia);
			}
		}}}
	}
		 
	//Second phase (2- for those element with numLink=1)		
	for (int i=0; i<Coordinator.KNumCH; i++)
	{
		for (int j=0; j<MB.NumEntity; j++){
			if (MB.entities.get(j).getLocalName().toString().toLowerCase().equals("laminar")){
				int wait2=0;
			}
			if (NumLickConcept[i][j] == 1) {
				addRoot(MB.entities.get(j).toString(), i);
				numAloneElemnt [i] = numAloneElemnt [i] +1;
				// add it in NumLinkConcept till do not add twice one statements to Thing
				 // we count those classes that are connected to alone_element
				 Iterator<Node> listStm = MB.rbgmModel.listStmtNodes();
				 while (listStm.hasNext()){
					 Node st= listStm.next();
					if (st.getPredicate().getLocalName().toLowerCase().equals("subclassof") ){
					 if (st.getSubject().getLocalName() != null && st.getObject().getLocalName() != null){
						 if (st.getSubject() == MB.entities.get(j)){
							 int isx= MB.findIndex(st.getObject().getLocalName());
							 if ((isx>0) && (uriToClusterID.get(st.getObject().toString()) != null))  NumLickConcept[i][isx] = NumLickConcept[i][isx] +2;
						 }
						 if (st.getObject() == MB.entities.get(j)){
							 int isx= MB.findIndex(st.getSubject().getLocalName());
							 if ((isx>0) && (uriToClusterID.get(st.getSubject().toString()) != null) )  NumLickConcept[i][isx] = NumLickConcept[i][isx] +2;
						 }
					 }
					}
				 }
			}
		}
	}
}

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
private boolean ExistinClusterTest (Node inode, int NumCluster ){
	boolean test = false;
	List ilist=new ArrayList(); 
	ilist =  models.get(NumCluster).listClasses().toList();
	for (int i=0; i< ilist.size(); i++){
		if (ilist.get(i).toString().equals(inode.toString())){
			test = true; 
			return test;
		}
	}
	//System.out.println(test);
	return test;
}
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
private void ConnectAloneElement(Node alone_element,int indexCH_aloneElement, int ia){
	addRoot(alone_element.toString(),indexCH_aloneElement ); //add this element in the ch block
	 numAloneElemnt [indexCH_aloneElement] = numAloneElemnt [indexCH_aloneElement] +1; 
	 //since we add one link in the file (alone_elemenet, subClassOf, "Thing"), so, we should count one link for alone_element in the NumLickConcept array 
	 NumLickConcept[indexCH_aloneElement][ia] = NumLickConcept[indexCH_aloneElement][ia] +2; //in the next lines, if this array home==1, then it thinks it is alone and does not link to Thing class, so, we add (+2) till it does not be equal 1
	 // we count those classes that are connected to alone_element
	 Iterator<Node> listStm = MB.rbgmModel.listStmtNodes();
	 while (listStm.hasNext()){
		 Node st= listStm.next();
		if (st.getPredicate().getLocalName().toLowerCase().equals("subclassof") ){
		 if (st.getSubject().getLocalName() != null && st.getObject().getLocalName() != null){
			 if (st.getSubject() == alone_element){
				 int isx= MB.findIndex(st.getObject().getLocalName());
				 if ((isx>0 && isx<=numEntity) && (uriToClusterID.get(st.getObject().toString()) != null) )  NumLickConcept[indexCH_aloneElement][isx] = NumLickConcept[indexCH_aloneElement][isx] +2;
			 }
			 if (st.getObject() == alone_element){
				 int isx= MB.findIndex(st.getSubject().getLocalName());
				 if ((isx>0 && isx<=numEntity) && (uriToClusterID.get(st.getSubject().toString()) != null) )  NumLickConcept[indexCH_aloneElement][isx] = NumLickConcept[indexCH_aloneElement][isx] +2;
			 }
		 }
		}
	 }
}





///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////AddingRoot_Phase //////////////////////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
public static void addRoot(String concept, int NumCluster){
	
	OntModel block = models.get(NumCluster);
	Resource subjectNew =  ResourceFactory.createResource(concept); 
	Property predicateNew  = ResourceFactory.createProperty("http://www.w3.org/2000/01/rdf-schema#subClassOf");
	RDFNode objectNew = ResourceFactory.createResource("http://www.w3.org/2002/07/owl#Thing");
	Statement statementNew = block.createStatement(subjectNew,  predicateNew, objectNew);
	block.add(statementNew);
}


/// based on the local modularity 
   public ArrayList<OntModel> createModules()
   {
	
	 ArrayList<Cluster> list = new ArrayList<Cluster>();
	 String moduletype[]= new String[]{"UM","LM","LUM","DCM","DRM"}; 
	 String onName=MB.getOntoName();// .nameOnt;
     Set<String> signatureNames = new HashSet<String>();
     ModulesGenerator MC; 
     OWLOntology owlN=null;
	 for (Iterator<Cluster> i = clusters.values().iterator(); i.hasNext();) 
	 {
	     list.add(i.next());  
	 }
	 
	 for(int i=0;i<list.size();i++)
	 {
		 Cluster cluster = list.get(i);
		 signatureNames.addAll(cluster.getURI());
		 String outPath = tempDir + ontName + "_Module_" + i + ".owl";
		 MC=new   ModulesGenerator(onName, signatureNames, moduletype[2], outPath);
		 owlN=MC.getModule();
		 signatureNames = new HashSet<String>();
		 saveOntology(owlN,outPath);
		 modelNames.add(outPath);
	 }	 
	 
	 //used during modules quality evaluation
	 numTree=new double[models.size()];
		for(int i=0;i<models.size();i++)
		 {
			  List Trlist=new ArrayList();
			  OntModel mod=models.get(i);
			  OntClass thng = mod.getOntClass( OWL.Thing.getURI() );
			  Trlist=thng.listSubClasses(true).toList();
			  if(list!=null) numTree[i]=Trlist.size(); 
		 }
	System.out.println("Modularization is done!!");
	return models; 
}



   /// based on the local modularity 
   public ArrayList<OntModel> createModules_E()
   {
	
	 ArrayList<Cluster> list = new ArrayList<Cluster>();
	 int moduletype[]= new int[]{0,1,2}; 
	 ArrayList<String> signatureNames = new ArrayList<String>();
     Extractor MC=new Extractor(); 
	 String onName=MB.getOntoName();// .nameOnt;
     OWLOntology owlN=null;
     int k=0;
	 for (Iterator<Cluster> i = clusters.values().iterator(); i.hasNext();) 
	 {
	     Cluster cluster = i.next();
		 signatureNames.addAll(cluster.getURI());
		 String outPath = tempDir + ontName + "_Module_" + k + ".owl"; k++;
		 owlN=MC.run(onName, signatureNames, moduletype[0]);
	   	 signatureNames = new ArrayList<String>();
		 saveOntology(owlN,outPath);
		 modelNames.add(outPath);
	 }	 
	 //used during modules quality evaluation
	 numTree=new double[models.size()];
		for(int i=0;i<models.size();i++)
		 {
			  List Trlist=new ArrayList();
			  OntModel mod=models.get(i);
			  OntClass thng = mod.getOntClass( OWL.Thing.getURI() );
			  Trlist=thng.listSubClasses(true).toList();
			  if(list!=null) numTree[i]=Trlist.size(); 
		 }
	System.out.println("Modularization is done!!");
	return models; 
}

}
