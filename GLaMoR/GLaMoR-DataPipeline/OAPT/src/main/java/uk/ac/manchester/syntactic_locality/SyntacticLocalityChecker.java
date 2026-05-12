package uk.ac.manchester.syntactic_locality;

import java.util.Iterator;
import java.util.Set;

import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.IRI;
import org.semanticweb.owlapi.model.OWLAnnotationAssertionAxiom;
import org.semanticweb.owlapi.model.OWLAnnotationPropertyDomainAxiom;
import org.semanticweb.owlapi.model.OWLAnnotationPropertyRangeAxiom;
import org.semanticweb.owlapi.model.OWLAnonymousIndividual;
import org.semanticweb.owlapi.model.OWLAsymmetricObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLAxiom;
import org.semanticweb.owlapi.model.OWLAxiomVisitor;
import org.semanticweb.owlapi.model.OWLClass;
import org.semanticweb.owlapi.model.OWLClassAssertionAxiom;
import org.semanticweb.owlapi.model.OWLClassExpression;
import org.semanticweb.owlapi.model.OWLClassExpressionVisitor;
import org.semanticweb.owlapi.model.OWLDataAllValuesFrom;
import org.semanticweb.owlapi.model.OWLDataExactCardinality;
import org.semanticweb.owlapi.model.OWLDataHasValue;
import org.semanticweb.owlapi.model.OWLDataMaxCardinality;
import org.semanticweb.owlapi.model.OWLDataMinCardinality;
import org.semanticweb.owlapi.model.OWLDataOneOf;
import org.semanticweb.owlapi.model.OWLDataPropertyAssertionAxiom;
import org.semanticweb.owlapi.model.OWLDataPropertyDomainAxiom;
import org.semanticweb.owlapi.model.OWLDataPropertyExpression;
import org.semanticweb.owlapi.model.OWLDataPropertyRangeAxiom;
import org.semanticweb.owlapi.model.OWLDataSomeValuesFrom;
import org.semanticweb.owlapi.model.OWLDatatypeDefinitionAxiom;
import org.semanticweb.owlapi.model.OWLDeclarationAxiom;
import org.semanticweb.owlapi.model.OWLDifferentIndividualsAxiom;
import org.semanticweb.owlapi.model.OWLDisjointClassesAxiom;
import org.semanticweb.owlapi.model.OWLDisjointDataPropertiesAxiom;
import org.semanticweb.owlapi.model.OWLDisjointObjectPropertiesAxiom;
import org.semanticweb.owlapi.model.OWLDisjointUnionAxiom;
import org.semanticweb.owlapi.model.OWLEntity;
import org.semanticweb.owlapi.model.OWLEquivalentClassesAxiom;
import org.semanticweb.owlapi.model.OWLEquivalentDataPropertiesAxiom;
import org.semanticweb.owlapi.model.OWLEquivalentObjectPropertiesAxiom;
import org.semanticweb.owlapi.model.OWLFunctionalDataPropertyAxiom;
import org.semanticweb.owlapi.model.OWLFunctionalObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLHasKeyAxiom;
import org.semanticweb.owlapi.model.OWLImportsDeclaration;
import org.semanticweb.owlapi.model.OWLInverseFunctionalObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLInverseObjectPropertiesAxiom;
import org.semanticweb.owlapi.model.OWLIrreflexiveObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLNegativeDataPropertyAssertionAxiom;
import org.semanticweb.owlapi.model.OWLNegativeObjectPropertyAssertionAxiom;
import org.semanticweb.owlapi.model.OWLObjectAllValuesFrom;
import org.semanticweb.owlapi.model.OWLObjectComplementOf;
import org.semanticweb.owlapi.model.OWLObjectExactCardinality;
import org.semanticweb.owlapi.model.OWLObjectHasSelf;
import org.semanticweb.owlapi.model.OWLObjectHasValue;
import org.semanticweb.owlapi.model.OWLObjectIntersectionOf;
import org.semanticweb.owlapi.model.OWLObjectMaxCardinality;
import org.semanticweb.owlapi.model.OWLObjectMinCardinality;
import org.semanticweb.owlapi.model.OWLObjectOneOf;
import org.semanticweb.owlapi.model.OWLObjectPropertyAssertionAxiom;
import org.semanticweb.owlapi.model.OWLObjectPropertyDomainAxiom;
import org.semanticweb.owlapi.model.OWLObjectPropertyExpression;
import org.semanticweb.owlapi.model.OWLObjectPropertyRangeAxiom;
import org.semanticweb.owlapi.model.OWLObjectSomeValuesFrom;
import org.semanticweb.owlapi.model.OWLObjectUnionOf;
import org.semanticweb.owlapi.model.OWLOntologyManager;
import org.semanticweb.owlapi.model.OWLReflexiveObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLSameIndividualAxiom;
import org.semanticweb.owlapi.model.OWLSubAnnotationPropertyOfAxiom;
import org.semanticweb.owlapi.model.OWLSubClassOfAxiom;
import org.semanticweb.owlapi.model.OWLSubDataPropertyOfAxiom;
import org.semanticweb.owlapi.model.OWLSubObjectPropertyOfAxiom;
import org.semanticweb.owlapi.model.OWLSubPropertyChainOfAxiom;
import org.semanticweb.owlapi.model.OWLSymmetricObjectPropertyAxiom;
import org.semanticweb.owlapi.model.OWLTransitiveObjectPropertyAxiom;
import org.semanticweb.owlapi.model.SWRLRule;


/**
 * This class re-implements the syntactic locality checker, based on the codes from Bernardo Cuenca, 
 * using the OWLAxiomVisitor class and the current version of the OWL API  *  
 * http://web.comlab.ox.ac.uk/oucl/work/bernardo.cuenca.grau/Software.html
 * For theoretical basis see "Modular Reuse of Ontologies: Theory and Practice".
 * Bernardo Cuenca Grau , Ian Horrocks , Yevgeny Kazakov , and Ulrike Sattler.
 * Journal of Artificial Intelligence Research (JAIR), Vol. 31, pp 273-318, 2008.
 * @author Ernesto Jimenez
 * Temporal Knowledge Bases Group
 * Jaume I University of Castellon
 * Created: 04/03/2008
 * Modified: -
 */
public class SyntacticLocalityChecker implements OWLAxiomVisitor {
    
    private boolean local;
    
    private OWLOntologyManager manager = OWLManager.createOWLOntologyManager();

    private String suggestedInformation;
    
    //private boolean dualConcepts;
    
    //private boolean dualRoles;
    
    //public static final int BOTTOM_LOCALITY = 1;
    
    //public static final int TOP_LOCALITY = 2;
    
    

    private PositiveOWLClassExpressionVisitor positiveOWLClassExpressionChecker;
    private NegativeOWLClassExpressionVisitor negativeOWLClassExpressionChecker;
    
    private Set<OWLEntity> foreignSignature;// = new HashSet<OWLEntity>();
    
    private boolean dualRoles;
    private boolean dualConcepts;
    
    private boolean considerEntityAnnotations;
    
    //It may be interesting when assertions are used as annotations
    private boolean ignoreAssertions;
    
    
    
    /**
     * Currently only supported bottom or dual interpretations, no support for 'id' interpretation
     * @param dualClasses
     * @param dualProperties
     * @param considerAnnotations Used for module extraction. Perhaps the user is interested in the annotations
     */
    //public SyntacticLocalityChecker(int localityInterpretation){
    public SyntacticLocalityChecker(boolean dualClasses, boolean dualProperties, boolean considerAnnotations, boolean ignoreAssertions){
        
        /*boolean dual = (localityInterpretation == TOP_LOCALITY);
        dualConcepts = dual;
        dualRoles = dual;*/
        dualConcepts = dualClasses;
        dualRoles = dualProperties;
        
        considerEntityAnnotations=considerAnnotations;
        this.ignoreAssertions=ignoreAssertions;
        
        positiveOWLClassExpressionChecker = new PositiveOWLClassExpressionVisitor();
        negativeOWLClassExpressionChecker = new NegativeOWLClassExpressionVisitor();
        
    }
    
    /**
     * Method used for locality chcking where annotations are always local
     * @param dualClasses
     * @param dualProperties
     */
    public SyntacticLocalityChecker(boolean dualClasses, boolean dualProperties){
        this(dualClasses, dualProperties, false, false);
    }
    
    
    

    
    /**
     * Information about why the axiom is non-local
     * @return
     */
    public String suggestions() {
        return suggestedInformation;
    }
    
    /**
     * To put outside? In a Locality Utils, where checkers are defined??
     * @param axiom
     * @param signature
     * @return
     */
    public boolean isLocalAxiom(OWLAxiom axiom, Set<OWLEntity> signature) {
        
        //Filter axioms??--> They are filtered within the segmenter
        //Review!!!
        //foreignSignature.clear();
        //foreignSignature=new HashSet<OWLEntity>(signature);
        //foreignSignature.addAll(signature);
        foreignSignature=signature;
        //positiveOWLClassExpressionChecker.setSignature(foreignSignature);
        //negativeOWLClassExpressionChecker.setSignature(foreignSignature);
        axiom.accept( this );
        return local;
    }
    
    
    private OWLClass Nothing() {
        return manager.getOWLDataFactory().getOWLNothing();
    }
    
    private OWLClass Thing() {
        return manager.getOWLDataFactory().getOWLThing();
    }

    
    /**
     * Method to be called inside visitors
     * @param classDescription
     * @return
     */
    private boolean isNegativeOWLClassExpression(OWLClassExpression classDescription) {
        classDescription.accept(negativeOWLClassExpressionChecker);
        return negativeOWLClassExpressionChecker.isNegativeDescription();
    }
    
    /**
     * Method to be called inside visitors
     * @param classDescription
     * @return
     */
    private boolean isPositiveOWLClassExpression(OWLClassExpression classDescription) {
        classDescription.accept(positiveOWLClassExpressionChecker);
        return positiveOWLClassExpressionChecker.isPositiveDescription();
        
    }
    
    
    /*public boolean dualRoles(){
        return dualRoles;
    }*/



    
    /*
     * ------------------------------------------------
     * ASSERTION AXIOMS
     * -------------------------------------------------
     * 
     */
    /**
     * Axioms of type a:C
     */
    public void visit(OWLClassAssertionAxiom axiom) {
        
        //if ignoreAssertions the is always local 
        local = ignoreAssertions || isPositiveOWLClassExpression(axiom.getClassExpression());
        
        suggestedInformation= "An OWLClassAssertionAxiom is local (bottom or dual) if the class description is 'Positive', " +
                "considering foreign entities both top and bottom.";
        
    }
    
    
    /**
     * Opposite case to OWLObjectPropertyAssertionAxiom for Top Locality
     * (no R )(a, b)) -->  ??
     */
    public void visit(OWLNegativeDataPropertyAssertionAxiom axiom) {
        //local = false;
        local = ignoreAssertions;
        suggestedInformation="An OWLNegativeDataPropertyAssertionAxiom is always non-local.";
    }
    
    
    
    /**
     * Opposite case to OWLObjectPropertyAssertionAxiom for Top Locality
     * (no R )(a, b)) --> ??
     */
    public void visit(OWLNegativeObjectPropertyAssertionAxiom axiom) {
        //local = false;
        local = ignoreAssertions;
        suggestedInformation="An OWLNegativeObjectPropertyAssertionAxiom is always non-local.";
    }

    /**
     * OWLObjectPropertyAssertionAxiom is dual-local iff the property doesn't belong to the signature.
     * Notice that this axiom is always non bottom local
     */
    public void visit(OWLObjectPropertyAssertionAxiom axiom) {
        
        local = ignoreAssertions || (dualRoles && !foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()));
        suggestedInformation="An OWLObjectPropertyAssertionAxiom could be dual-local if the property doesn't belong to the external signature";
        
    }

    /**
     * OWLObjectPropertyAssertionAxiom is dual-local iff the property doesn't belong to the signature.
     * Notice that this axiom are always non bottom local
     */
    public void visit(OWLDataPropertyAssertionAxiom axiom) {
        
        local = ignoreAssertions || (dualRoles && !foreignSignature.contains(axiom.getProperty().asOWLDataProperty()));
        suggestedInformation="An OWLDataPropertyAssertionAxiom could be dual-local if the property doesn't belong to the external signature";
        
    }
    
    /**
     * 
     */
    public void visit(OWLSameIndividualAxiom axiom) {
        //local = false;
        local = ignoreAssertions;
        suggestedInformation="An OWLSameIndividualsAxiom is always non-local.";
    }
    
    /**
     * 
     */
    public void visit(OWLDifferentIndividualsAxiom axiom) {
        //local = false;
        local = ignoreAssertions;
        suggestedInformation="An OWLDifferentIndividualsAxiom is always non-local.";
    }
    
    /*End Assertion Axioms*/
    //------------------------------------------------------------------------

    
    
    
    
    
    
    
    /*
     * ------------------------------------------------
     * CLASS AXIOMS
     * -------------------------------------------------
     * 
     */

    /**
     * Both dual and bottom has the same hehaviour 
     */
    public void visit(OWLSubClassOfAxiom axiom) {
        
        local = isNegativeOWLClassExpression( axiom.getSubClass())
            || isPositiveOWLClassExpression( axiom.getSuperClass());

        suggestedInformation="An OWLSubClassAxiom is local if 'the subclass description is Negative' or " +
            "'the superclass description is Positive'.";        
    }


    /**
     * Both dual and bottom has the same hehaviour 
     */
    public void visit(OWLDisjointClassesAxiom axiom) {
        
        suggestedInformation="An OWLDisjointClassesAxiom is local if at least one of the involved descriptions is" +
            "Negative.";
        
        //At least one description is bottom
        //A dij B --> (A intersection B) subClassOf bottom
        Set<OWLClassExpression> disjclasses = axiom.getClassExpressions();
        if (disjclasses.size()<=1) {  //We could consider the intersection with the empty set 
            local=true;
            return;
        }
        else {
            for(OWLClassExpression clsDesc : disjclasses) {
                if(isNegativeOWLClassExpression(clsDesc)){
                    local = true;
                    return;
                }
            }
        }
        
        local=false;
    }
    
    
    /**
     * Both dual and bottom has the same hehaviour 
     */
    public void visit(OWLEquivalentClassesAxiom axiom) {
        
        Set<OWLClassExpression> eqclasses = axiom.getClassExpressions();

        if(eqclasses.size() == 1){
            local=true;
        }
        else if(eqclasses.size() == 2){
            Iterator iter = eqclasses.iterator();
            OWLClassExpression first = (OWLClassExpression)iter.next();
            OWLClassExpression second = (OWLClassExpression)iter.next();
            if ((isNegativeOWLClassExpression(first)
                    || isPositiveOWLClassExpression(second)) && 
                    (isNegativeOWLClassExpression(second)
                    || isPositiveOWLClassExpression(first)))
                local = true;
            else
                local = false;
            
        }
        else {
            
            Object[] classDescriptions = eqclasses.toArray();
            
            
            for (int i=0; i<classDescriptions.length-1; i++) {
                for (int j=i+1; j<classDescriptions.length; j++) {
                    local = (isNegativeOWLClassExpression((OWLClassExpression)classDescriptions[i])
                            || isPositiveOWLClassExpression((OWLClassExpression)classDescriptions[j])) && 
                            (isNegativeOWLClassExpression((OWLClassExpression)classDescriptions[j])
                            || isPositiveOWLClassExpression((OWLClassExpression)classDescriptions[i]));
                    
                    if (!local) //All the cases had to keep the condition
                        return;
                    
                }
            }
        }
        
        suggestedInformation="An OWLEquivalentClassesAxiom is local if both sides of the axiom have the same " +
            "value, or Negative or Positive. It could be also considered as a combined subClassOf axiom.";
    }
    
    
    
    /**
     * OWLDisjointUnionAxiom  A eq B union C union D..., bein B, C, D,... disjoint classes.
     * Therefore we should guarantee the locality both for the equivalence and for the disjointness
     * 
     */
    public void visit(OWLDisjointUnionAxiom axiom) {
        
        
        suggestedInformation="We should guarantee the locality both for the equivalence and for the disjointness.";
        
        
        //Treatment of equivalence with the union
        OWLClassExpression unionDesc = manager.getOWLDataFactory().getOWLObjectUnionOf(axiom.getClassExpressions());
        
        if ((isNegativeOWLClassExpression(axiom.getOWLClass())
                || isPositiveOWLClassExpression(unionDesc)) && 
                (isNegativeOWLClassExpression(unionDesc)
                || isPositiveOWLClassExpression(axiom.getOWLClass()))) {
            local = true;
        }
        else {  //It is not necessary to continue
            local = false;
            return;
        }
        
        
        //Treatment of disjointness
        for(OWLClassExpression clsDesc : axiom.getClassExpressions()) {
            if(isNegativeOWLClassExpression(clsDesc)){
                local = true; //plus locality in the equivalence
                return;
            }
        }
    
        local=false;
        

    }
    
    
    ///END CLASS AXIOMS
    
    
    
    
    
    
    
    /*
     * -----------------------------------------
     * PROPERTY AXIOMS
     * -----------------------------------------
     * 
     */
    /**
     * OWLObjectSubPropertyAxiom
     */
    public void visit(OWLSubObjectPropertyOfAxiom axiom) {
        
        //Bottom locality R^(bottom) subOf R
        if(!dualRoles && !foreignSignature.contains(axiom.getSubProperty().asOWLObjectProperty()))
            local = true;
        
        //Top Locality: R subOf R^(top x top)
        else if(dualRoles && !foreignSignature.contains(axiom.getSuperProperty().asOWLObjectProperty()))
            local = true;
        
        else
            local = false;
    }
    
    
    /**
     * OWLDataSubPropertyAxiom
     */
    public void visit(OWLSubDataPropertyOfAxiom axiom) {
        
        //Bottom locality R^(bottom) subOf R
        if(!dualRoles && !foreignSignature.contains(axiom.getSubProperty().asOWLDataProperty()))
            local = true;
        
        //Top Locality: R subOf R^(top x top)
        else if(dualRoles && !foreignSignature.contains(axiom.getSuperProperty().asOWLDataProperty()))
            local = true;
        
        else
            local = false;
        
    }
    
    
    public void visit(OWLEquivalentDataPropertiesAxiom axiom) {
        
        //For both cases: dual and bottom
        suggestedInformation="An OWLEquivalentDataPropertiesAxiom is local if non external properties are involved.";
        
        for(OWLDataPropertyExpression dataPropExp : axiom.getProperties()) {
            if(foreignSignature.contains(dataPropExp.asOWLDataProperty())){
                local=false;
                return;
            }
        }
        local=true;
        
    }

    
    public void visit(OWLEquivalentObjectPropertiesAxiom axiom) {
        //For both cases: dual and bottom
        suggestedInformation="An OWLEquivalentObjectPropertiesAxiom is local if non external properties are involved.";
        
        for(OWLObjectPropertyExpression dataPropExp : axiom.getProperties()) {
            if(foreignSignature.contains(dataPropExp.asOWLObjectProperty())){
                local=false;
                return;
            }
        }
        local=true;
        
    }
    
    
    /**
     * OWLDisjointDataPropertiesAxiom always non-local
     */
    public void visit(OWLDisjointDataPropertiesAxiom axiom) {
        local = false;
        suggestedInformation="An OWLDisjointDataPropertiesAxiom is always non local.";
    }
    
    
    /**
     * OWLDisjointObjectPropertiesAxiom always non-local
     */
    public void visit(OWLDisjointObjectPropertiesAxiom axiom) {
        local = false;
        suggestedInformation="An OWLDisjointObjectPropertiesAxiom is always non local.";
    }

    
    
    /**
     * Non local for dual locality.
     * For bottom locality is local iff property does not belong to the external signature
     */
    public void visit(OWLFunctionalDataPropertyAxiom axiom) {
        if(!foreignSignature.contains(axiom.getProperty().asOWLDataProperty()) && !dualRoles)
            local = true;
        else
            local = false; //Non Local for dual locality
    
        suggestedInformation="A OWLFunctionalDataPropertyAxiom axiom can only be bottom local iff property does not belong to the external signature.";
        
    }

    /**
     * Non local for dual locality.
     * For bottom locality is local iff proerty does not belong to the external signature
     */
    public void visit(OWLFunctionalObjectPropertyAxiom axiom) {
        if(!foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()) && !dualRoles)
            local = true;
        else
            local = false; //Non Local for dual locality
        
        suggestedInformation="A OWLFunctionalObjectPropertyAxiom axiom can only be bottom local iff property does not belong to the external signature.";
    }


    public void visit(OWLInverseFunctionalObjectPropertyAxiom axiom) {
        if(!foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()) && !dualRoles)
            local = true;
        else
            local = false; //Non Local for dual locality
        
        suggestedInformation="A OWLInverseFunctionalObjectPropertyAxiom axiom can only be bottom local iff property does not belong to the external signature.";
    }

    
    /**
     * Both properties involved in the inverse axiom shouldn't belong to the external signature 
     */
    public void visit(OWLInverseObjectPropertiesAxiom axiom) {
        if(!foreignSignature.contains(axiom.getFirstProperty().asOWLObjectProperty()) && 
                !foreignSignature.contains(axiom.getSecondProperty().asOWLObjectProperty()))
            local = true;
        else
            local = false;
        
        suggestedInformation="A OWLInverseObjectPropertiesAxiom axiom is local iff the involved property do not belong to the external signature.";

    }

    /**
     * An irreflexive (or aliorelative) relation R is one where for all a in X, a is never R-related to itself
     */
    public void visit(OWLIrreflexiveObjectPropertyAxiom axiom) {
        if(!foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()))
            local = true;
        else
            local = false;
        
        suggestedInformation="A OWLIrreflexiveObjectPropertyAxiom axiom is local iff property does not belong to the external signature.";

    }

    /**
     * 
     */
    public void visit(OWLAsymmetricObjectPropertyAxiom axiom) {
        if(!foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()))
            local = true;
        else
            local = false;
        
        suggestedInformation="A OWLAntiSymmetricObjectPropertyAxiom axiom is local iff property does not belong to the external signature.";

    }
    
    /**
     * A reflexive relation R on set C is one where for all a in C, a is R-related to itself (R(a,a)).
     */
    public void visit(OWLReflexiveObjectPropertyAxiom axiom) {
        if(!foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()))
            local = true;
        else
            local = false;
        
        suggestedInformation="A OWLSymmetricObjectPropertyAxiom axiom is local iff property does not belong to the external signature.";
        
    }
    
    /**
     * Similar to inverse...
     */
    public void visit(OWLSymmetricObjectPropertyAxiom axiom) {
        if(!foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()))
            local = true;
        else
            local = false;
        
        suggestedInformation="A OWLSymmetricObjectPropertyAxiom axiom is local iff property does not belong to the external signature.";
    }

    /**
     * 
     */
    public void visit(OWLTransitiveObjectPropertyAxiom axiom) {
        //Bottom and dual
        if(!foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()))
            local = true;
        else
            local = false;
        
        suggestedInformation="A OWLFunctionalObjectPropertyAxiom axiom is local iff property does not belong to the external signature.";
        
    }
    
    
    /**
     * Different in codes from Clark & Parsia!!
     */
    public void visit(OWLDataPropertyDomainAxiom axiom) {
        
        //Dual && bottom
        if(isPositiveOWLClassExpression(axiom.getDomain()))
            local=true;
        //Bottom
        else if(!foreignSignature.contains(axiom.getProperty().asOWLDataProperty()) && !dualRoles)
            local=true;
        else
            local=false;
        
        suggestedInformation="";
    }
    
    /**
     * Different in codes from Clark & Parsia!!
     */
    public void visit(OWLObjectPropertyDomainAxiom axiom) {
        
        //Dual && bottom
        if(isPositiveOWLClassExpression(axiom.getDomain()))
            local=true;
        //Bottom
        else if(!foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()) && !dualRoles)
            local=true;
        else
            local=false;    
        
        suggestedInformation="";
    }

    
    /**
     * Different in codes from Clark & Parsia!!
     */
    public void visit(OWLObjectPropertyRangeAxiom axiom) {
        //Dual && Bottom
        if(isPositiveOWLClassExpression(axiom.getRange()))
            local=true;
        //Bottom
        else if(!foreignSignature.contains(axiom.getProperty().asOWLObjectProperty()) && !dualRoles)
            local = true;
        else
            local=false;
            
        suggestedInformation="";
    }

    
    
    /**
     * Different in codes from Clark & Parsia!!
     */
    public void visit(OWLDataPropertyRangeAxiom axiom) {
        if(!foreignSignature.contains(axiom.getProperty().asOWLDataProperty()) && !dualRoles)
            local=true;
        else
            local=false;
        
        suggestedInformation="An OWLDataPropertyRangeAxiom can only be bottom local if the property does not belong to the external signature.";;
    }
    

    
    
    /**
     * 
     */
    public void visit(OWLSubPropertyChainOfAxiom axiom) {
        //Encadenamiento de propiedades....
        //Book hasArticles Articles hasAuthors Individuals
        // and chain(hasArticles, hasAuthors) subOf hasBookAuthors
        //so Book hasBookAuthors Individuals
        //local = false;
        //suggestedInformation="An OWLObjectPropertyChainSubPropertyAxiom is always non-local.";
        
        
        //Similar to subproperty axiom
        suggestedInformation="A OWLObjectPropertyChainSubPropertyAxiom axiom is local iff involved properties do not belong to the external signature.";
        //Bottom locality R^(bottom) subOf R
        if(!dualRoles){
            for (OWLObjectPropertyExpression propExp : axiom.getPropertyChain()){
                /*
                 * Got:
                 * Exception in thread "main" org.semanticweb.owlapi.model.OWLRuntimeException: Property is not a named property.  Check using the isAnonymous method before calling this method!
                 * at uk.ac.manchester.cs.owl.owlapi.OWLObjectInverseOfImpl.asOWLObjectProperty(OWLObjectInverseOfImpl.java:124)
                 * at uk.ac.manchester.syntactic_locality.SyntacticLocalityChecker.visit(SyntacticLocalityChecker.java:692)
                 * at uk.ac.manchester.cs.owl.owlapi.OWLSubPropertyChainAxiomImpl.accept(OWLSubPropertyChainAxiomImpl.java:128)
                 * at uk.ac.manchester.syntactic_locality.SyntacticLocalityChecker.isLocalAxiom(SyntacticLocalityChecker.java:117)
                 * at uk.ac.manchester.syntactic_locality.ModuleExtractor.extractModuleAxiomsForEntity(ModuleExtractor.java:569)
                 * at uk.ac.manchester.syntactic_locality.ExtractModules4OntologyEntities.<init>(ExtractModules4OntologyEntities.java:229)
                 * at uk.ac.manchester.syntactic_locality.ExtractModules4OntologyEntities.main(ExtractModules4OntologyEntities.java:359)
                 *
                 * and thus added the !propExp.isAnonymous() check 
                 */
                if (!propExp.isAnonymous() && foreignSignature.contains(propExp.asOWLObjectProperty())){
                    local = false;
                    return;
                }
            }
            local = true;
        }
            
        
        //Top Locality: R subOf R^(top x top)
        else if(dualRoles && !foreignSignature.contains(axiom.getSuperProperty().asOWLObjectProperty()))
            local = true;
        
        else
            local = false;
        
        
        
        
    }

    
    //End Properry Axioms
    //---------------------------------------------------------------

    
    
    
    
    /*
     * ----------------------
     * ANNOTATION AXIOMS
     * Local=true, for locality checking, but for module extraction we could be interested in the extraction
     * ----------------------
     */
    
    public void visit(OWLAnnotationAssertionAxiom axiom){
        
        local = true;
        
        if (axiom.getSubject() instanceof IRI){

            if (foreignSignature.contains(manager.getOWLDataFactory().getOWLClass((IRI)axiom.getSubject()))
                    || foreignSignature.contains(manager.getOWLDataFactory().getOWLObjectProperty((IRI)axiom.getSubject()))
                    || foreignSignature.contains(manager.getOWLDataFactory().getOWLDataProperty((IRI)axiom.getSubject()))){
                
                
                
                if (axiom.getAnnotation().getValue() instanceof IRI){ //Named individual (used in FMA)
                    local = ignoreAssertions || !considerEntityAnnotations;
                }
                else if (axiom.getAnnotation().getValue() instanceof OWLAnonymousIndividual){ //Anonymous individual (used in OBO ontologies)
                    local = ignoreAssertions || !considerEntityAnnotations;
                }
                else {
                    local=!considerEntityAnnotations;
                }
            }
        }       
        //The other option is to be and anonymous individual (used by FMA, and OBO ontos): they contain annotation for synonyms
        else if (axiom.getSubject() instanceof OWLAnonymousIndividual){
            
            //check if instance was included
            //if (!axiom.getSubject().toString().matches(".+#genid[0-9]+")){
            //  System.out.println(axiom.getSubject().toString());
            //}
            
            local = ignoreAssertions || !considerEntityAnnotations;
            
        }
        
        
        
    }
    
    
    
    public void visit(OWLSubAnnotationPropertyOfAxiom axiom){
        //Bottom locality R^(bottom) subOf R
        if(!dualRoles && !foreignSignature.contains(axiom.getSubProperty()))
            local = true;
        
        //Top Locality: R subOf R^(top x top)
        else if(dualRoles && !foreignSignature.contains(axiom.getSuperProperty()))
            local = true;
        
        else
            local = false;
        
    }
    
    public void visit(OWLAnnotationPropertyDomainAxiom axiom){
        //Dual && bottom
        /*if(isPositiveOWLClassExpression(axiom.get.getDomain().))
            local=true;
        //Bottom
        else*/ if(!foreignSignature.contains(axiom.getProperty()) && !dualRoles)
            local=true;
        else
            local=false;
        
        suggestedInformation="";
    }
    
    public void visit(OWLAnnotationPropertyRangeAxiom axiom){
        if(!foreignSignature.contains(axiom.getProperty()) && !dualRoles)
            local=true;
        else
            local=false;
        
        suggestedInformation="An OWLAnnotationPropertyRangeAxiom can only be bottom local if the property does not belong to the external signature.";;
    }
    
    
    
    //OLD ones deprecated in OWL 2.0
    /*public void visit(OWLOntologyAnnotationAxiom axiom) {
        //local=!considerEntityAnnotations;
        local = true;
    }
    
    public void visit(OWLAxiomAnnotationAxiom axiom) {
        //local=!considerEntityAnnotations;
        local = true;
    }
    
    
    public void visit(OWLEntityAnnotationAxiom axiom) {
        local = true;
        
        //Only if annotation belongs to external sig 
        if (foreignSignature.contains(axiom.getSubject()))
            local=!considerEntityAnnotations;
        
    }*/

    
    /*END ANNOTATIONS
     ------------------------------------*/
    
    
    /*
     * OTHERS
     */
    /**
     * Why is non local??
     */
    public void visit(OWLImportsDeclaration axiom) {
        local = false; //We should not consider this axioms
    }

    /**
     * A Declaration Axiom only introduces an entity in the ontology it has not logical significance
     a:C and R(a,b)??
     */
    public void visit(OWLDeclarationAxiom axiom) {
        //local=true;
        //isLocal = !(axiom.getEntity() instanceof OWLIndividual);
        suggestedInformation="An OWLDeclarationAxiom is local if the declared entity does not belongs to the foreign signature.";
        local = !foreignSignature.contains(axiom.getEntity());
    }
    
    public void visit(SWRLRule axiom) {
        local = false;
        suggestedInformation="Currently, a SWRLRule axiom is always considered non-local.";
    }
    
    
    public void visit(OWLHasKeyAxiom axiom){
        local = false;
        suggestedInformation="Currently, a HasKey axiom is always considered non-local.";

    }

    public void visit(OWLDatatypeDefinitionAxiom axiom){
        local = false;
        suggestedInformation="Currently, a OWLDatatypeDefinition axiom is always considered non-local.";

    }    
    
    
    
    
    
    
    /**
     * A re-implementation of the method "isPositivelyLocal" from Bernardo's code using the OWLClassExpressionVisitor
     * Cons(BOTTOM)
     * @author Ernesto
     * Temporal Knowledge Bases Group
     * Jaume I University of Castellon
     * Created: 04/03/2008
     * Modified: -
     */
    private class NegativeOWLClassExpressionVisitor implements OWLClassExpressionVisitor {

        //boolean dualConcepts;
        //boolean dualRoles;
        
        boolean isNegativeDescription;
        
        //Set<OWLEntity> foreignSignature;
        
        
        public NegativeOWLClassExpressionVisitor(){
            
        }
        
        
        //public void setSignature(Set<OWLEntity> signature){
        //  foreignSignature=signature;
        //}
        
        

        public boolean isNegativeDescription(){
            return isNegativeDescription;
        }

        
        
        public void visit(OWLClass desc) {
            
            //Bottom and dual
            if (desc.equals(Nothing()))
                isNegativeDescription = true;
            else if (!foreignSignature.contains(desc) && !dualConcepts) //Only for bottom
                isNegativeDescription = true;
            else
                isNegativeDescription = false;
            
        }

        /**
         * INTERSECTIONOF: At least one conjunct must be negative to make the intersection bottom
         */
        public void visit(OWLObjectIntersectionOf desc) {
            
            for (OWLClassExpression clsDesc : desc.getOperands()) {
                if (isNegativeOWLClassExpression(clsDesc)){
                    isNegativeDescription = true;
                    return;
                }
            }
            isNegativeDescription=false;
            
        }


        /**
         * UNIONOF: All disjuncts must be negative
         */
        public void visit(OWLObjectUnionOf desc) {

            for (OWLClassExpression clsDesc : desc.getOperands()){
                if (!isNegativeOWLClassExpression(clsDesc)){
                    isNegativeDescription = false;
                    return;
                }
            }
            isNegativeDescription = true;
        }
        

        /**
         * COMPLEMENTOF: not C^Top
         */
        public void visit(OWLObjectComplementOf desc) {
            isNegativeDescription = isPositiveOWLClassExpression(desc.getOperand());
        }
        

        /**
         * ONEOF: Always non local?
         */
        public void visit(OWLObjectOneOf desc) {
            isNegativeDescription = false;
        }
        
        
        /**
         * ONEOF: Always non local?
         */
        public void visit(OWLDataOneOf desc) {
            isNegativeDescription = false;
        }


        




        /**
         *  OBJECT ALL RESTRICTIONS
         */
        public void visit(OWLObjectAllValuesFrom desc) {
            
            //Only for dual
            if (dualRoles && isNegativeOWLClassExpression(desc.getFiller()) 
                    && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                isNegativeDescription=true;
            
            //Bottom is always false
            //"All Restrictions" are always non Negative (non empty), since any class that does not uses the
            //property is going to belong to this set
            else
                isNegativeDescription=false;
          
        }
        
        
        /**
         *  DATA ALL RESTRICTIONS 
         */
        public void visit(OWLDataAllValuesFrom desc) {
            //DataRanges (desc.getFiller()) are evaluated as Negative or Positive --> ??
            //In Clark&parsia codes is considered false --> Range class is literal (outside signature) then --> Top
            //isNegativeDescription=false;
            
            
            //Only mixed
            if (dualRoles && !dualConcepts && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isNegativeDescription=true;
        
            //Bottom is always false
            //"All Restrictions" are always non Negative (non empty), since any class that does not uses the
            //property is going to belong to this set
            else
                isNegativeDescription=false;
                
        }
        
        
        /**
         * OBJECT SOME RESTRICTION
         */
        public void visit(OWLObjectSomeValuesFrom desc) {
            
            //Bottom and Dual
            if (isNegativeOWLClassExpression(desc.getFiller()))
                isNegativeDescription=true;
            //Only bottom
            else if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                isNegativeDescription=true;
            else
                isNegativeDescription=false;
            
        }
        

        /**
         * DATA SOME RESTRICTION
         */
        public void visit(OWLDataSomeValuesFrom desc) {
            
            //Only bottom concepts
            if (!dualConcepts)
                isNegativeDescription=true;  //If Literals are considered as bottom
            //Only bottom roles
            else if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isNegativeDescription=true;
            else
                isNegativeDescription=false;
        }

        
        /**
         * SELF RESTRICTION: C belongs (some??)R.C
         */
        public void visit(OWLObjectHasSelf desc) {
            //Only bottom
            //For dual: if prop are not in signature --> Top
            if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                isNegativeDescription = true;
            else
                isNegativeDescription = false;
        }

        

        /**
         * OBJECT VALUE RESTRICTION
         */
        public void visit(OWLObjectHasValue desc) {
            //Only bottom
            //For dual: if prop are not in signature --> Top
            if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()) &&
                    !foreignSignature.contains(desc.getValue()))
                isNegativeDescription = true;
            else
                isNegativeDescription = false;
            
        }
        
        
        
        /**
         * DATA VALUE RESTRICTION
         */
        public void visit(OWLDataHasValue desc) {
            //Only bottom
            //For dual: if prop are not in signature --> Top
            if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isNegativeDescription = true;
            else
                isNegativeDescription = false;          
        }

        
        /*
         * CARDINALITIES
         */     
        public void visit(OWLObjectMinCardinality desc) {
            
            //Adaptation to OWL 1.1 with qualified number restrictions (cardinalities)
            if (desc.isQualified()) {
                //Bottom and Dual
                if (isNegativeOWLClassExpression(desc.getFiller()))
                    isNegativeDescription=true;
                //Only bottom
                else if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                    isNegativeDescription=true;
                else
                    isNegativeDescription=false;
            }
            
            //Non qualified cardinalities
            else {
                if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                    isNegativeDescription=true;
                else
                    isNegativeDescription=false;
            }
            
        }
        
        
        public void visit(OWLDataMinCardinality desc) {
            
            //Only bottom concepts
            if (!dualConcepts)
                isNegativeDescription=true;  //If Literals are considered as bottom
            else if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isNegativeDescription=true;
            else
                //For Dual always is false
                ////Range class is literal (outside signature) then --> Top 
                isNegativeDescription=false;
        }
        


        /* NOTE:
         * Max card Restrictions are always non Negative (considering external entities as bottom), since any class that does not uses the property 
         * is going to belong to this set. Similar to all restrictions, we present a maximum or a rule that we mustn't violate.
         * "Some restrictions" and "Min cardinality" presents necesary restrictions to be preserved that we must keep or fulfil
         */
        public void visit(OWLObjectMaxCardinality desc) {
            
            //Adaptation to OWL 1.1 with qualified number restrictions (cardinalities)
            if (desc.isQualified()) {
                //Only for dual
                if (dualRoles && isNegativeOWLClassExpression(desc.getFiller()) 
                        && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                    isNegativeDescription=true;
                
                //Bottom is always false
                //"Max Restrictions" are always non Negative (non empty), since any class that does not uses the
                //property is going to belong to this set
                else
                    isNegativeDescription=false;
            }
            else {
                
                if (dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                    isNegativeDescription=true;
                
                //Bottom is always false
                //"Max Restrictions" are always non Negative (non empty), since any class that does not uses the
                //property is going to belong to this set
                else
                    isNegativeDescription=false;    
            }
            
            
        }

        public void visit(OWLDataMaxCardinality desc) {
            
            //DataRanges (desc.getFiller()) are evaluated as Negative or Positive --> ??
            //In Clark&parsia codes is considered false --> Range class is literal (outside signature) then --> Top 
        
            
            //Only mixed
            if (dualRoles && !dualConcepts && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isNegativeDescription=true;
        
            //Bottom is always false
            //"All Restrictions" are always non Negative (non empty), since any class that does not uses the
            //property is going to belong to this set
            else
                isNegativeDescription=false;
            
        }

        public void visit(OWLObjectExactCardinality desc) {
            
            //Adaptation to OWL 1.1 with qualified number restrictions (cardinalities)
            if (desc.isQualified()) {
                
                //Both duaRoles and nonDual 
                if (isNegativeOWLClassExpression(desc.getFiller()) && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                    isNegativeDescription=true;
                
                else
                    isNegativeDescription=false;
            }
            else {
                if (!foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                    isNegativeDescription=true;
                
                else
                    isNegativeDescription=false;    
            }
            
        }

        
        public void visit(OWLDataExactCardinality desc) {
            //If Literals are considered as bottom
            //Review!!
            if (!dualConcepts && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isNegativeDescription=true;
                
            else
                isNegativeDescription=false;
            
        }
    
    }

    
    
    
    
    
    
    
    
    
    
    
    /**
     * A re-implementation of the method "isNegativelyyLocal" from Bernardo's code using the OWLClassExpressionVisitor
     * Cons(TOP)
     * @author Ernesto
     * Temporal Knowledge Bases Group
     * Jaume I University of Castellon
     * Created: 04/03/2008
     * Modified: -
     */
    private class PositiveOWLClassExpressionVisitor implements OWLClassExpressionVisitor {

        //boolean dualConcepts;
        //boolean dualRoles;
        
        boolean isPositiveDescription;
        
        //Set<OWLEntity> foreignSignature;
        
        
        public PositiveOWLClassExpressionVisitor(){
            
        }

        
        public boolean isPositiveDescription(){
            return isPositiveDescription;
        }
        
        
        //public void setSignature(Set<OWLEntity> signature){
        //  foreignSignature=signature;
        //}
        
        
        /**
         * OWLCLASS: 
         */
        public void visit(OWLClass desc) {
            
            //Bottom and Dual
            if (desc.equals(Thing()))
                isPositiveDescription = true;
            //Only Top: A^Top
            else if (dualConcepts && !foreignSignature.contains(desc))
                isPositiveDescription=true;
            else
                isPositiveDescription=false;
        }
        
        


        /**
         * INTERSECTION: All conjuncts must be positive
         */
        public void visit(OWLObjectIntersectionOf desc) {
            
            //All conjuncts must be positive
            for (OWLClassExpression clsDesc : desc.getOperands()){
                if (!isPositiveOWLClassExpression(clsDesc)){
                    isPositiveDescription = false;
                    return;
                }
            }
            isPositiveDescription = true;   
        }

        

        /**
         * UNION: At least one of the disjuncts must be positive
         */
        public void visit(OWLObjectUnionOf desc) {

            //At least one of the disjuncts must be positive
            for (OWLClassExpression clsDesc : desc.getOperands()){
                if (isPositiveOWLClassExpression(clsDesc)) {
                    isPositiveDescription = true;
                    return;
                }
    
            }
            isPositiveDescription = false;  
        }
        


        /**
         * COMPLEMENT: not C^bottom
         */
        public void visit(OWLObjectComplementOf desc) {
            
            isPositiveDescription = isNegativeOWLClassExpression(desc.getOperand());
            
        }
        
        
        /**
         * ONEOF: alway false??
         */
        public void visit(OWLObjectOneOf desc) {
            isPositiveDescription = false;
        }
        
        /**
         * ONEOF: Always non local?
         */
        public void visit(OWLDataOneOf desc) {
            isPositiveDescription = false;
        }




        


        public void visit(OWLObjectAllValuesFrom desc) {
            
            //All
            if (isPositiveOWLClassExpression(desc.getFiller()))
                isPositiveDescription = true;
            //Only for bottom roles
            else if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                isPositiveDescription = true;
            else
                isPositiveDescription = false;
            
        }
        
        
        public void visit(OWLDataAllValuesFrom desc) {
            
            //Only dual concepts since literal values are interpreted as Top
            if (dualConcepts)
                isPositiveDescription = true;
            //Only for bottom roles
            else if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isPositiveDescription = true;
            else
                isPositiveDescription = false;
        }


        
        public void visit(OWLObjectSomeValuesFrom desc) {
            
            if (dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty())
                    && isPositiveOWLClassExpression(desc.getFiller()))
                isPositiveDescription = true;
            else
                isPositiveDescription = false;
            
        }
        
        public void visit(OWLDataSomeValuesFrom desc) {
            //Both duals, since literal range should be considered as Top
            if (dualRoles && dualConcepts && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isPositiveDescription = true;
            else
                isPositiveDescription = false;
        }

        /**
         * SELF RESTRICTION: C belongs (some??)R.C
         */
        public void visit(OWLObjectHasSelf desc) {
                isPositiveDescription = false;  //We don't know about the class
        }
        
        

        /**
         * OBJECT VALUE RESTRICTION
         */
        public void visit(OWLObjectHasValue desc) {
            //Only dual
            //For dual: if prop are not in signature --> Top
            if (dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()) &&
                    !foreignSignature.contains(desc.getValue()))
                isPositiveDescription = true;
            else
                isPositiveDescription = false;
            
        }
        
        
        
        /**
         * DATA VALUE RESTRICTION
         */
        public void visit(OWLDataHasValue desc) {
            //Only dual
            //For dual: if prop are not in signature --> Top
            if (dualRoles && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isPositiveDescription = true;
            else
                isPositiveDescription = false;          
        }
        
        


        
        public void visit(OWLObjectMinCardinality desc) {
            
            if (desc.isQualified()){
                if (dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()) 
                    && isPositiveOWLClassExpression(desc.getFiller()))
                    isPositiveDescription = true;
                else
                    isPositiveDescription = false;
            }
            else {
                if (dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                    isPositiveDescription = true;
                else
                    isPositiveDescription = false;
            }
            
        }

        public void visit(OWLDataMinCardinality desc) {
            
            //Both duals, since literal range should be considered as Top
            if (dualRoles && dualConcepts && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isPositiveDescription = true;
            else
                isPositiveDescription = false;
            
            
        }


        public void visit(OWLObjectMaxCardinality desc) {
            //All
            if (isPositiveOWLClassExpression(desc.getFiller()))
                isPositiveDescription = true;
            //Only for bottom roles
            else if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                isPositiveDescription = true;
            else
                isPositiveDescription = false;
            
        }

        
        public void visit(OWLDataMaxCardinality desc) {
            
            if (desc.isQualified()) {
                //Only dual concepts since literal values are interpreted as Top
                if (dualConcepts)
                    isPositiveDescription = true;
                //Only for bottom roles
                else if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                    isPositiveDescription = true;
                else
                    isPositiveDescription = false;
            }
            else {
                if (!dualRoles && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                    isPositiveDescription = true;
                else
                    isPositiveDescription = false;
            }
        }   
            
            
       
        public void visit(OWLObjectExactCardinality desc) {
            
            //Idem than MInCardinality
            if (desc.isQualified()) {
                if (dualRoles && !foreignSignature.contains(desc.getProperty()) && isPositiveOWLClassExpression(desc.getFiller()))
                    isPositiveDescription = true;
                else
                    isPositiveDescription = false;
                                
            }
            else {
                if (dualRoles && !foreignSignature.contains(desc.getProperty().asOWLObjectProperty()))
                    isPositiveDescription = true;
                else
                    isPositiveDescription = false;
       
            }
        }
        
        public void visit(OWLDataExactCardinality desc) {
        
            //Both duals, since literal range should be considered as Top
            if (dualRoles && dualConcepts && !foreignSignature.contains(desc.getProperty().asOWLDataProperty()))
                isPositiveDescription = true;
            else
                isPositiveDescription = false;
            
        }


        
    }

    
    


}
