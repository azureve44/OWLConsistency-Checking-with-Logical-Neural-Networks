package anti_pattern.implementations;
import anti_pattern.Anti_Pattern;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;
import java.util.*;
import java.util.stream.Collectors;
public class UEWIP implements Anti_Pattern {
    private final OWLDataFactory dataFactory;
    public UEWIP() {
        OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
        dataFactory = manager.getOWLDataFactory();
    }
    /**
     * c2 ⊑ ∃R1.c1, c1 ⊑ ∀R2.c3, R1 = R2^-1, Disj(c2, c3)
     */
    @Override
    public Optional<List<OWLAxiom>> checkForPossiblePatternCompletion(OWLOntology ontology) {
        Optional<OWLInverseObjectPropertiesAxiom> possibleResult = findInjectableInversePropertyAxioms(ontology);
        if (possibleResult.isPresent()) return Optional.of(List.of(possibleResult.get()));
        Optional<OWLSubClassOfAxiom> possibleSubClassOfAxiomInjection = findInjectableSubClassOfAxioms(ontology);
        if (possibleSubClassOfAxiomInjection.isPresent()) return Optional.of(List.of(possibleSubClassOfAxiomInjection.get()));
        Optional<OWLDisjointClassesAxiom> possibleDisjointClassesAxiomInjection = findInjectableDisjointClassesAxioms(ontology);
        if (possibleDisjointClassesAxiomInjection.isPresent()) return Optional.of(List.of(possibleDisjointClassesAxiomInjection.get()));
        return Optional.empty();
    }
    private Optional<OWLInverseObjectPropertiesAxiom> findInjectableInversePropertyAxioms(OWLOntology ontology) {
        for (OWLDisjointClassesAxiom axiom : ontology.getAxioms(AxiomType.DISJOINT_CLASSES)) {
            Set<OWLClassExpression> classExpressions = axiom.getClassExpressions();
            OWLClassExpression c1 = null;
            OWLObjectPropertyExpression r1 = null;
            Set<OWLSubClassOfAxiom> existsRestriction = ontology.axioms(AxiomType.SUBCLASS_OF)
                    .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_SOME_VALUES_FROM))
                    .collect(Collectors.toSet());
            Set<OWLSubClassOfAxiom> forAllRestriction = ontology.axioms(AxiomType.SUBCLASS_OF)
                    .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_ALL_VALUES_FROM))
                    .collect(Collectors.toSet());
            for (OWLSubClassOfAxiom subClassOfAxiom : existsRestriction) {
                OWLClassExpression superClass = subClassOfAxiom.getSuperClass();
                if (!(superClass instanceof OWLObjectSomeValuesFrom)) continue;
                OWLObjectSomeValuesFrom someValuesFrom = (OWLObjectSomeValuesFrom) superClass;
                if (classExpressions.contains(subClassOfAxiom.getSubClass())) {
                    c1 = someValuesFrom.getFiller();
                    r1 = someValuesFrom.getProperty();
                }
            }
            if (c1 == null || r1 == null) continue;
            for (OWLSubClassOfAxiom subClassForAll : forAllRestriction) {
                OWLClassExpression superForAll = subClassForAll.getSuperClass();
                if (!(superForAll instanceof OWLObjectAllValuesFrom)) continue;
                OWLObjectAllValuesFrom allValuesFrom = (OWLObjectAllValuesFrom) superForAll;
                if (classExpressions.contains(allValuesFrom.getFiller())
                        && subClassForAll.getSubClass().equals(c1)) {
                    OWLObjectPropertyExpression r2 = allValuesFrom.getProperty();
                    return Optional.of(dataFactory.getOWLInverseObjectPropertiesAxiom(r1, r2));
                }
            }
        }
        return Optional.empty();
    }
    private Optional<OWLSubClassOfAxiom> findInjectableSubClassOfAxioms(OWLOntology ontology) {
        for (OWLInverseObjectPropertiesAxiom inverseAxiom : ontology.getAxioms(AxiomType.INVERSE_OBJECT_PROPERTIES)) {
            OWLObjectPropertyExpression r1 = inverseAxiom.getFirstProperty();
            OWLObjectPropertyExpression r2 = inverseAxiom.getSecondProperty();
            for (OWLSubClassOfAxiom subClassOfAxiom : ontology.getAxioms(AxiomType.SUBCLASS_OF)) {
                OWLClassExpression superClass = subClassOfAxiom.getSuperClass();
                if (!(superClass instanceof OWLObjectSomeValuesFrom)) continue;
                OWLObjectSomeValuesFrom someValuesFrom = (OWLObjectSomeValuesFrom) superClass;
                if (!someValuesFrom.getProperty().equals(r1)) continue;
                OWLClassExpression c2 = subClassOfAxiom.getSubClass();
                OWLClassExpression c1 = someValuesFrom.getFiller();
                for (OWLDisjointClassesAxiom disjointClassesAxiom : ontology.getAxioms(AxiomType.DISJOINT_CLASSES)) {
                    if (!disjointClassesAxiom.getClassExpressions().contains(c2)) continue;
                    Set<OWLClassExpression> others = new HashSet<>(disjointClassesAxiom.getClassExpressions());
                    others.remove(c2);
                    if (others.isEmpty()) continue;
                    OWLClassExpression c3 = others.iterator().next();
                    return Optional.of(dataFactory.getOWLSubClassOfAxiom(c1, dataFactory.getOWLObjectAllValuesFrom(r2, c3)));
                }
            }
        }
        return Optional.empty();
    }
    private Optional<OWLDisjointClassesAxiom> findInjectableDisjointClassesAxioms(OWLOntology ontology) {
        for (OWLInverseObjectPropertiesAxiom inverseAxiom : ontology.getAxioms(AxiomType.INVERSE_OBJECT_PROPERTIES)) {
            OWLObjectPropertyExpression r1 = inverseAxiom.getFirstProperty();
            OWLObjectPropertyExpression r2 = inverseAxiom.getSecondProperty();
            Set<OWLSubClassOfAxiom> existsRestriction = ontology.axioms(AxiomType.SUBCLASS_OF)
                    .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_SOME_VALUES_FROM))
                    .collect(Collectors.toSet());
            Set<OWLSubClassOfAxiom> forAllRestriction = ontology.axioms(AxiomType.SUBCLASS_OF)
                    .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_ALL_VALUES_FROM))
                    .collect(Collectors.toSet());
            OWLClassExpression c1 = null;
            OWLClassExpression c2 = null;
            OWLClassExpression c3 = null;
            for (OWLSubClassOfAxiom subClassOfAxiom : existsRestriction) {
                OWLClassExpression superClass = subClassOfAxiom.getSuperClass();
                if (!(superClass instanceof OWLObjectSomeValuesFrom)) continue;
                OWLObjectSomeValuesFrom someValuesFrom = (OWLObjectSomeValuesFrom) superClass;
                if (someValuesFrom.getProperty().equals(r1)) {
                    c1 = someValuesFrom.getFiller();
                    c2 = subClassOfAxiom.getSubClass();
                }
            }
            if (c1 == null) continue;
            for (OWLSubClassOfAxiom forAllSubClass : forAllRestriction) {
                OWLClassExpression superClass = forAllSubClass.getSuperClass();
                if (!(superClass instanceof OWLObjectAllValuesFrom)) continue;
                OWLObjectAllValuesFrom allValuesFrom = (OWLObjectAllValuesFrom) superClass;
                if (forAllSubClass.getSubClass().equals(c1)
                        && allValuesFrom.getProperty().equals(r2)) {
                    c3 = allValuesFrom.getFiller();
                }
            }
            if (c2 != null && c3 != null && !c2.equals(c3)) {
                return Optional.of(dataFactory.getOWLDisjointClassesAxiom(c2, c3));
            }
        }
        return Optional.empty();
    }
    @Override
    public String getName() {
        return "UEWIP";
    }
}
