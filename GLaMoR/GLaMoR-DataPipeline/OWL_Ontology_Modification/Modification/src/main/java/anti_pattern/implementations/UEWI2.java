package anti_pattern.implementations;
import anti_pattern.Anti_Pattern;
import anti_pattern.Util;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;
import java.util.*;
import java.util.stream.Collectors;
public class UEWI2 implements Anti_Pattern {
    private final OWLDataFactory dataFactory;
    public UEWI2() {
        OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
        dataFactory = manager.getOWLDataFactory();
    }
    @Override
    public Optional<List<OWLAxiom>> checkForPossiblePatternCompletion(OWLOntology ontology) {
        for (OWLSubClassOfAxiom axiom : ontology.getAxioms(AxiomType.SUBCLASS_OF)) {
            OWLClassExpression c1 = axiom.getSubClass();
            OWLClassExpression c2 = axiom.getSuperClass();
            if (c1.getClassExpressionType().equals(ClassExpressionType.OWL_CLASS)
                    && c2.getClassExpressionType().equals(ClassExpressionType.OWL_CLASS)) {
                Set<OWLClassExpression> possibleC3 = Util.findFillersOfObjectSomeValuesFromAxioms(ontology, c2, c1);
                Set<OWLClassExpression> possibleC4 = Util.findFillersOfObjectAllValuesFromAxioms(ontology, c1, c2);
                if (!(possibleC3.isEmpty() || possibleC4.isEmpty())) {
                    return Optional.of(List.of(dataFactory.getOWLDisjointClassesAxiom(possibleC3.iterator().next(), possibleC4.iterator().next())));
                }
            }
        }
        for (OWLSubClassOfAxiom axiom : ontology.getAxioms(AxiomType.SUBCLASS_OF)) {
            OWLClassExpression c1 = axiom.getSubClass();
            OWLClassExpression c2 = axiom.getSuperClass();
            if (c1.getClassExpressionType().equals(ClassExpressionType.OWL_CLASS)
                    && c2.getClassExpressionType().equals(ClassExpressionType.OWL_CLASS)) {
                Optional<OWLSubClassOfAxiom> possibleInjection = Util.findPossibleInjectionBasedOnSubClassAxiomWithSomeRestriction(ontology, c2, c1, dataFactory);
                if (possibleInjection.isPresent()) return Optional.of(List.of(possibleInjection.get()));
                possibleInjection = Util.findPossibleInjectionBasedOnSubClassAxiomWithAllRestriction(ontology, c1, c2, dataFactory);
                if (possibleInjection.isPresent()) return Optional.of(List.of(possibleInjection.get()));
            }
        }
        for (OWLDisjointClassesAxiom axiom : ontology.getAxioms(AxiomType.DISJOINT_CLASSES)) {
            Set<OWLClassExpression> classes = axiom.getClassExpressions();
            Set<OWLSubClassOfAxiom> possibleSubClassAxioms = ontology.axioms(AxiomType.SUBCLASS_OF)
                    .filter(subClassOfAxiom -> subClassOfAxiom.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_ALL_VALUES_FROM))
                    .filter(subClassOfAxiom -> classes.contains(((OWLObjectAllValuesFrom) subClassOfAxiom.getSuperClass()).getFiller()))
                    .collect(Collectors.toSet());
            for (OWLSubClassOfAxiom possibleSubClassAxiom : possibleSubClassAxioms) {
                OWLObjectAllValuesFrom allRestriction = (OWLObjectAllValuesFrom) possibleSubClassAxiom.getSuperClass();
                OWLObjectPropertyExpression property = allRestriction.getProperty();
                OWLClassExpression c1 = possibleSubClassAxiom.getSubClass();
                OWLClassExpression c3 = allRestriction.getFiller();
                Set<OWLSubClassOfAxiom> foundPattern = ontology
                        .axioms(AxiomType.SUBCLASS_OF)
                        .filter(subClassOfAxiom -> subClassOfAxiom.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_SOME_VALUES_FROM))
                        .filter(subClassOfAxiom -> classes.contains(((OWLObjectSomeValuesFrom) subClassOfAxiom.getSuperClass()).getFiller()))
                        .filter(subClassOfAxiom -> ((OWLObjectSomeValuesFrom) subClassOfAxiom.getSuperClass()).getProperty().equals(property))
                        .filter(subClassOfAxiom -> !subClassOfAxiom.getSubClass().equals(c1))
                        .map(subClassOfAxiom -> (OWLObjectSomeValuesFrom) subClassOfAxiom.getSuperClass())
                        .map(OWLObjectSomeValuesFrom::getFiller)
                        .filter(c4 -> !c4.equals(c3))
                        .map(c4 -> dataFactory.getOWLSubClassOfAxiom(c1, c4))
                        .collect(Collectors.toSet());
                if (!foundPattern.isEmpty()) {
                    return Optional.of(List.of(foundPattern.iterator().next()));
                }
            }
        }
        return Optional.empty();
    }
    @Override
    public String getName() {
        return "UEWI2";
    }
}
