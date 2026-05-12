package anti_pattern.implementations;

import anti_pattern.Anti_Pattern;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;

import java.util.*;
import java.util.stream.Collectors;

public class OOD implements Anti_Pattern {

    private final OWLDataFactory dataFactory;
    private final OWLOntologyManager manager;
    public OOD() {
        this.manager = OWLManager.createOWLOntologyManager();
        this.dataFactory = manager.getOWLDataFactory();
    }

    /**
     * Pattern:  c1 = 𝐷𝑜𝑚𝑎𝑖𝑛(𝑝), 𝑝(𝑎, 𝑏, c), 𝑎∈𝑐2, 𝐷𝑖𝑠𝑗(𝑐1, 𝑐2)
     * O
     * @param ontology
     * @return
     */
    @Override
    public Optional<List<OWLAxiom>> checkForPossiblePatternCompletion(OWLOntology ontology) {
        Optional<OWLObjectPropertyDomainAxiom> possibleDomainInjection = findInjectableDomainAxiom(ontology, manager);
        if(possibleDomainInjection.isPresent()) return Optional.of(List.of(possibleDomainInjection.get()));

        Optional<OWLDisjointClassesAxiom> possibleDisjointClassesInjection = findInjectableDisjointClassesAxiom(ontology, manager);
        if(possibleDisjointClassesInjection.isPresent()) return Optional.of(List.of(possibleDisjointClassesInjection.get()));

        Optional<OWLClassAssertionAxiom> possibleClassAssertionInjection = findInjectableClassAssertionAxiom(ontology, manager);
        if(possibleClassAssertionInjection.isPresent()) return Optional.of(List.of(possibleClassAssertionInjection.get()));

        Optional<OWLObjectPropertyAssertionAxiom> possiblePropertyAssertionAxiomInjection = findInjectableObjectPropertyAssertionAxiom(ontology, manager);
        if(possiblePropertyAssertionAxiomInjection.isPresent()) return Optional.of(List.of(possiblePropertyAssertionAxiomInjection.get()));
        return Optional.empty();
    }




    /**
     * c1 = 𝐷𝑜𝑚𝑎𝑖𝑛(𝑝), o∈𝑐2, 𝐷𝑖𝑠𝑗(𝑐1, 𝑐2) in Ontology -> Return  p(o, p, s)
     * @param ontology
     * @param manager
     * @return
     */
    private Optional<OWLObjectPropertyAssertionAxiom> findInjectableObjectPropertyAssertionAxiom(OWLOntology ontology, OWLOntologyManager manager){
        Set<OWLObjectPropertyDomainAxiom> domainAxiomSet = ontology.getAxioms(AxiomType.OBJECT_PROPERTY_DOMAIN);
        if(domainAxiomSet.isEmpty()) return Optional.empty();
        Set<OWLDisjointClassesAxiom> disjointClassesAxiomSet = ontology.getAxioms(AxiomType.DISJOINT_CLASSES);
        if(disjointClassesAxiomSet.isEmpty()) return Optional.empty();

        for(OWLObjectPropertyDomainAxiom domainAxiom: domainAxiomSet){
            OWLClassExpression possibleC1 = domainAxiom.getDomain();
            OWLObjectPropertyExpression possibleP = domainAxiom.getProperty();
            Set<OWLDisjointClassesAxiom> possibleDisjointClassesAxioms = disjointClassesAxiomSet.stream().filter(ax -> ax.getClassExpressions().contains(possibleC1)).collect(Collectors.toSet());

            for(OWLDisjointClassesAxiom disjointClassesAxiom : possibleDisjointClassesAxioms){
                Set<OWLClassExpression> possibleC2s = disjointClassesAxiom.getClassExpressions();
                if(!possibleC2s.remove(possibleC1)) continue;
                if(possibleC2s.isEmpty()) continue;

                OWLClassExpression c2 = possibleC2s.stream().findFirst().get();
                Set<OWLNamedIndividual> possibleAs = ontology.axioms(AxiomType.CLASS_ASSERTION).filter(ax-> ax.getIndividual().isOWLNamedIndividual())
                        .filter(ax -> ax.getClassExpression().equals(c2))
                        .map(ax -> ax.getIndividual().asOWLNamedIndividual())
                        .collect(Collectors.toSet());
                if(possibleAs.isEmpty()) continue;
                return Optional.of(manager.getOWLDataFactory().getOWLObjectPropertyAssertionAxiom( possibleP,possibleAs.iterator().next(), ontology.individualsInSignature().findFirst().get()));
            }

        }
        return Optional.empty();
    }


    /**
     * c1 = 𝐷𝑜𝑚𝑎𝑖𝑛(𝑝), p(o, p, s), 𝐷𝑖𝑠𝑗(𝑐1, 𝑐2) in Ontology -> Return o∈𝑐2
     * @param ontology
     * @param manager
     * @return
     */
    private Optional<OWLClassAssertionAxiom> findInjectableClassAssertionAxiom(OWLOntology ontology, OWLOntologyManager manager){
        Set<OWLObjectPropertyDomainAxiom> domainAxiomSet = ontology.getAxioms(AxiomType.OBJECT_PROPERTY_DOMAIN);
        if(domainAxiomSet.isEmpty()) return Optional.empty();
        Set<OWLObjectPropertyAssertionAxiom> propertyAxiomSet = ontology.getAxioms(AxiomType.OBJECT_PROPERTY_ASSERTION);
        if(propertyAxiomSet.isEmpty()) return Optional.empty();

        for(OWLObjectPropertyDomainAxiom propertyDomainAxiom : domainAxiomSet){
            OWLClassExpression possibleC1 = propertyDomainAxiom.getDomain();
            OWLObjectPropertyExpression possibleProperty = propertyDomainAxiom.getProperty();
            Set<OWLObjectPropertyAssertionAxiom> propertyAssertionAxioms = ontology.axioms(AxiomType.OBJECT_PROPERTY_ASSERTION).filter(ax -> ax.getProperty().equals(possibleProperty)).collect(Collectors.toSet());
            if(propertyAssertionAxioms.isEmpty()) continue;
            Set<OWLDisjointClassesAxiom> disjointClassesAxioms = ontology.axioms(AxiomType.DISJOINT_CLASSES).filter(ax -> ax.getClassExpressions().contains(possibleC1)).collect(Collectors.toSet());
            if(disjointClassesAxioms.isEmpty()) continue;
            for(OWLDisjointClassesAxiom disjointClassesAxiom : disjointClassesAxioms){
                Set<OWLClassExpression> possibleC2s = disjointClassesAxiom.getClassExpressions();
                possibleC2s.remove(possibleC1);
                if(possibleC2s.isEmpty()) continue;
                OWLClassExpression possibleC2 = possibleC2s.iterator().next();
                OWLNamedIndividual object = propertyAssertionAxioms.stream().findFirst().get().getObject().asOWLNamedIndividual();
                return Optional.of(manager.getOWLDataFactory().getOWLClassAssertionAxiom(possibleC2, object));
            }
        }
        return Optional.empty();
    }


    /**
     * c1 = 𝐷𝑜𝑚𝑎𝑖𝑛(𝑝), p(o, p, s), o∈𝑐2 in Ontology -> Return 𝐷𝑖𝑠𝑗(𝑐1, 𝑐2)
     * @param ontology
     * @param manager
     * @return
     */
    private Optional<OWLDisjointClassesAxiom> findInjectableDisjointClassesAxiom(OWLOntology ontology, OWLOntologyManager manager){
        Set<OWLObjectPropertyDomainAxiom> domainAxiomSet = ontology.getAxioms(AxiomType.OBJECT_PROPERTY_DOMAIN);
        if(domainAxiomSet.isEmpty()) return Optional.empty();
        Set<OWLObjectPropertyAssertionAxiom> propertyAxiomSet = ontology.getAxioms(AxiomType.OBJECT_PROPERTY_ASSERTION);
        if(propertyAxiomSet.isEmpty()) return Optional.empty();

        for(OWLObjectPropertyDomainAxiom propertyDomainAxiom : domainAxiomSet){
            OWLObjectPropertyExpression possibleProperty = propertyDomainAxiom.getProperty();
            OWLClassExpression possibleC1 = propertyDomainAxiom.getDomain();
            Set<OWLObjectPropertyAssertionAxiom> possibleRelevantPropertyAssertion = propertyAxiomSet.stream().filter(assertionAxiom -> assertionAxiom.getProperty().equals(possibleProperty)).collect(Collectors.toSet());
            if(possibleRelevantPropertyAssertion.isEmpty()) continue;

            for(OWLObjectPropertyAssertionAxiom propertyAssertionAxiom : possibleRelevantPropertyAssertion){
                OWLNamedIndividual possibleA = propertyAssertionAxiom.getObject().asOWLNamedIndividual();
                Set<OWLClassExpression> possibleC2 = ontology.axioms(AxiomType.CLASS_ASSERTION).filter(ax -> ax.getIndividual().equals(possibleA)).map(OWLClassAssertionAxiom::getClassExpression).collect(Collectors.toSet());
                if(possibleC2.isEmpty()) continue;
                return Optional.of(manager.getOWLDataFactory().getOWLDisjointClassesAxiom(possibleC1, possibleC2.iterator().next()));
            }
        }
        return Optional.empty();
    }
    /**
     * 𝐷𝑖𝑠𝑗(𝑐1, 𝑐2), p(o, p, s), o∈𝑐2 in Ontology -> Return c1 = 𝐷𝑜𝑚𝑎𝑖𝑛(𝑝),
     * @param ontology
     * @param manager
     * @return
     */
    private Optional<OWLObjectPropertyDomainAxiom> findInjectableDomainAxiom(OWLOntology ontology, OWLOntologyManager manager){
        Set<OWLObjectPropertyAssertionAxiom> propertyAxiomSet = ontology.getAxioms(AxiomType.OBJECT_PROPERTY_ASSERTION);
        if(propertyAxiomSet.isEmpty()) return Optional.empty();

        for(OWLObjectPropertyAssertionAxiom propertyAssertionAxiom : propertyAxiomSet){
            OWLObjectProperty property = propertyAssertionAxiom.getProperty().asOWLObjectProperty();
            OWLNamedIndividual individual =propertyAssertionAxiom.getObject().asOWLNamedIndividual();

            Set<OWLClassExpression> possibleC2 = ontology.axioms(AxiomType.CLASS_ASSERTION).filter(ax -> ax.getIndividual().equals(individual)).map(OWLClassAssertionAxiom::getClassExpression).collect(Collectors.toSet());
            if(possibleC2.isEmpty()) continue;
            Optional<OWLDisjointClassesAxiom> disjointClassesAxiomOpt = ontology.axioms(AxiomType.DISJOINT_CLASSES)
                    .filter(ax -> ax.getClassExpressions().stream().anyMatch(possibleC2::contains))
                    .findFirst();
            if(disjointClassesAxiomOpt.isEmpty()) return Optional.empty();

            OWLDisjointClassesAxiom disjointClassesAxiom = disjointClassesAxiomOpt.get();
            for(OWLClassExpression classExpression: disjointClassesAxiom.getClassExpressions()){
                if(!possibleC2.contains(classExpression)){
                    return Optional.of(manager.getOWLDataFactory().getOWLObjectPropertyDomainAxiom(property, classExpression));
                }
            }
        }
        return Optional.empty();
    }
    @Override
    public String getName() {
        return "OOD";
    }
}
