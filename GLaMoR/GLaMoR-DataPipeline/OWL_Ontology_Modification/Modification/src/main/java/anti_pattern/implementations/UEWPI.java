package anti_pattern.implementations;
import anti_pattern.Anti_Pattern;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;
import java.util.*;
import java.util.stream.Collectors;
public class UEWPI implements Anti_Pattern {
    private final OWLDataFactory dataFactory;
    public UEWPI() {
        OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
        dataFactory = manager.getOWLDataFactory();
    }
    /**
     * R1 ⊑ R2, c1 ⊑ ∃R1.c2, c1 ⊑ ∀R2.c3, Disj(c2, c3)
     */
    @Override
    public Optional<List<OWLAxiom>> checkForPossiblePatternCompletion(OWLOntology ontology) {
        Optional<OWLDisjointClassesAxiom> disjointResult = findInjectableDisjointClassAxioms(ontology);
        if (disjointResult.isPresent()) return Optional.of(List.of(disjointResult.get()));
        Optional<OWLSubClassOfAxiom> subClassForAllResult = findInjectableSubClassAxiomsWithForAllRestriction(ontology);
        if (subClassForAllResult.isPresent()) return Optional.of(List.of(subClassForAllResult.get()));
        Optional<OWLSubClassOfAxiom> subClassExistsResult = findInjectableSubClassAxiomsWithExistsRestriction(ontology);
        if (subClassExistsResult.isPresent()) return Optional.of(List.of(subClassExistsResult.get()));
        Optional<OWLSubObjectPropertyOfAxiom> propertyResult = findInjectableSubPropertyAxioms(ontology);
        if (propertyResult.isPresent()) return Optional.of(List.of(propertyResult.get()));
        return Optional.empty();
    }
    private Optional<OWLDisjointClassesAxiom> findInjectableDisjointClassAxioms(OWLOntology ontology) {
        Set<OWLSubObjectPropertyOfAxiom> subPropertyAxiomSet = ontology.getAxioms(AxiomType.SUB_OBJECT_PROPERTY);
        for (OWLSubObjectPropertyOfAxiom subPropertyAxiom : subPropertyAxiomSet) {
            OWLObjectPropertyExpression r1 = subPropertyAxiom.getSubProperty();
            OWLObjectPropertyExpression r2 = subPropertyAxiom.getSuperProperty();
            Set<OWLClassExpression> existsSubClasses = ontology.axioms(AxiomType.SUBCLASS_OF)
                    .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_SOME_VALUES_FROM))
                    .filter(ax -> ((OWLObjectSomeValuesFrom) ax.getSuperClass()).getProperty().equals(r1))
                    .map(OWLSubClassOfAxiom::getSubClass)
                    .collect(Collectors.toSet());
            Set<OWLClassExpression> forAllSubClasses = ontology.axioms(AxiomType.SUBCLASS_OF)
                    .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_ALL_VALUES_FROM))
                    .filter(ax -> ((OWLObjectAllValuesFrom) ax.getSuperClass()).getProperty().equals(r2))
                    .map(OWLSubClassOfAxiom::getSubClass)
                    .collect(Collectors.toSet());
            Set<OWLClassExpression> c1Candidates = new HashSet<>(existsSubClasses);
            c1Candidates.retainAll(forAllSubClasses);
            for (OWLClassExpression c1 : c1Candidates) {
                OWLClassExpression c2 = null;
                OWLClassExpression c3 = null;
                for (OWLSubClassOfAxiom subClassAxiom : ontology.getAxioms(AxiomType.SUBCLASS_OF)) {
                    if (!subClassAxiom.getSubClass().equals(c1)) continue;
                    OWLClassExpression superClass = subClassAxiom.getSuperClass();
                    if (superClass instanceof OWLObjectSomeValuesFrom) {
                        OWLObjectSomeValuesFrom someValuesFrom = (OWLObjectSomeValuesFrom) superClass;
                        if (someValuesFrom.getProperty().equals(r1)) {
                            c2 = someValuesFrom.getFiller();
                        }
                    }
                    if (superClass instanceof OWLObjectAllValuesFrom) {
                        OWLObjectAllValuesFrom allValuesFrom = (OWLObjectAllValuesFrom) superClass;
                        if (allValuesFrom.getProperty().equals(r2)) {
                            c3 = allValuesFrom.getFiller();
                        }
                    }
                }
                if (c2 != null && c3 != null && !c2.equals(c3)) {
                    return Optional.of(dataFactory.getOWLDisjointClassesAxiom(c2, c3));
                }
            }
        }
        return Optional.empty();
    }
    private Optional<OWLSubClassOfAxiom> findInjectableSubClassAxiomsWithForAllRestriction(OWLOntology ontology) {
        Set<OWLSubObjectPropertyOfAxiom> subPropertyAxiomSet = ontology.getAxioms(AxiomType.SUB_OBJECT_PROPERTY);
        for (OWLSubObjectPropertyOfAxiom subPropertyAxiom : subPropertyAxiomSet) {
            OWLObjectPropertyExpression r1 = subPropertyAxiom.getSubProperty();
            OWLObjectPropertyExpression r2 = subPropertyAxiom.getSuperProperty();
            Set<OWLClassExpression> c1Candidates = ontology.axioms(AxiomType.SUBCLASS_OF)
                    .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_SOME_VALUES_FROM))
                    .filter(ax -> ((OWLObjectSomeValuesFrom) ax.getSuperClass()).getProperty().equals(r1))
                    .map(OWLSubClassOfAxiom::getSubClass)
                    .collect(Collectors.toSet());
            for (OWLClassExpression c1 : c1Candidates) {
                for (OWLSubClassOfAxiom subClassAxiom : ontology.getAxioms(AxiomType.SUBCLASS_OF)) {
                    if (!subClassAxiom.getSubClass().equals(c1)) continue;
                    OWLClassExpression superClass = subClassAxiom.getSuperClass();
                    if (!(superClass instanceof OWLObjectSomeValuesFrom)) {
                        continue;
                    }
                    OWLObjectSomeValuesFrom someValuesFrom = (OWLObjectSomeValuesFrom) superClass;
                    if (!someValuesFrom.getProperty().equals(r1)) {
                        continue;
                    }
                    OWLClassExpression c2 = someValuesFrom.getFiller();
                    Set<OWLClassExpression> c3Candidates = ontology.axioms(AxiomType.DISJOINT_CLASSES)
                            .map(OWLNaryClassAxiom::getClassExpressions)
                            .filter(classExpressions -> classExpressions.contains(c2))
                            .flatMap(Set::stream)
                            .filter(candidate -> !candidate.equals(c2))
                            .collect(Collectors.toSet());
                    for (OWLClassExpression c3 : c3Candidates) {
                        return Optional.of(dataFactory.getOWLSubClassOfAxiom(c1, dataFactory.getOWLObjectAllValuesFrom(r2, c3)));
                    }
                }
            }
        }
        return Optional.empty();
    }
    private Optional<OWLSubClassOfAxiom> findInjectableSubClassAxiomsWithExistsRestriction(OWLOntology ontology) {
        Set<OWLSubObjectPropertyOfAxiom> subPropertyAxiomSet = ontology.getAxioms(AxiomType.SUB_OBJECT_PROPERTY);
        for (OWLSubObjectPropertyOfAxiom subPropertyAxiom : subPropertyAxiomSet) {
            OWLObjectPropertyExpression r1 = subPropertyAxiom.getSubProperty();
            OWLObjectPropertyExpression r2 = subPropertyAxiom.getSuperProperty();
            Set<OWLClassExpression> c1Candidates = ontology.axioms(AxiomType.SUBCLASS_OF)
                    .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_ALL_VALUES_FROM))
                    .filter(ax -> ((OWLObjectAllValuesFrom) ax.getSuperClass()).getProperty().equals(r2))
                    .map(OWLSubClassOfAxiom::getSubClass)
                    .collect(Collectors.toSet());
            for (OWLClassExpression c1 : c1Candidates) {
                for (OWLSubClassOfAxiom subClassAxiom : ontology.getAxioms(AxiomType.SUBCLASS_OF)) {
                    if (!subClassAxiom.getSubClass().equals(c1)) continue;
                    OWLClassExpression superClass = subClassAxiom.getSuperClass();
                    if (!(superClass instanceof OWLObjectAllValuesFrom)) {
                        continue;
                    }
                    OWLObjectAllValuesFrom allValuesFrom = (OWLObjectAllValuesFrom) superClass;
                    if (!allValuesFrom.getProperty().equals(r2)) {
                        continue;
                    }
                    OWLClassExpression c3 = allValuesFrom.getFiller();
                    Set<OWLClassExpression> c2Candidates = ontology.axioms(AxiomType.DISJOINT_CLASSES)
                            .map(OWLNaryClassAxiom::getClassExpressions)
                            .filter(classExpressions -> classExpressions.contains(c3))
                            .flatMap(Set::stream)
                            .filter(candidate -> !candidate.equals(c3))
                            .collect(Collectors.toSet());
                    for (OWLClassExpression c2 : c2Candidates) {
                        return Optional.of(dataFactory.getOWLSubClassOfAxiom(c1, dataFactory.getOWLObjectSomeValuesFrom(r1, c2)));
                    }
                }
            }
        }
        return Optional.empty();
    }
    private Optional<OWLSubObjectPropertyOfAxiom> findInjectableSubPropertyAxioms(OWLOntology ontology) {
        Set<OWLClassExpression> existsSubClasses = ontology.axioms(AxiomType.SUBCLASS_OF)
                .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_SOME_VALUES_FROM))
                .map(OWLSubClassOfAxiom::getSubClass)
                .collect(Collectors.toSet());
        if (existsSubClasses.isEmpty()) return Optional.empty();
        Set<OWLClassExpression> forAllSubClasses = ontology.axioms(AxiomType.SUBCLASS_OF)
                .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_ALL_VALUES_FROM))
                .map(OWLSubClassOfAxiom::getSubClass)
                .collect(Collectors.toSet());
        if (forAllSubClasses.isEmpty()) return Optional.empty();
        Set<OWLClassExpression> c1Candidates = new HashSet<>(existsSubClasses);
        c1Candidates.retainAll(forAllSubClasses);
        if (c1Candidates.isEmpty()) return Optional.empty();
        for (OWLClassExpression c1 : c1Candidates) {
            OWLClassExpression c2 = null;
            OWLClassExpression c3 = null;
            OWLObjectPropertyExpression r1 = null;
            OWLObjectPropertyExpression r2 = null;
            for (OWLSubClassOfAxiom subClassAxiom : ontology.getAxioms(AxiomType.SUBCLASS_OF)) {
                if (!subClassAxiom.getSubClass().equals(c1)) continue;
                OWLClassExpression superClass = subClassAxiom.getSuperClass();
                if (superClass instanceof OWLObjectSomeValuesFrom) {
                    OWLObjectSomeValuesFrom someValuesFrom = (OWLObjectSomeValuesFrom) superClass;
                    c2 = someValuesFrom.getFiller();
                    r1 = someValuesFrom.getProperty();
                }
                if (superClass instanceof OWLObjectAllValuesFrom) {
                    OWLObjectAllValuesFrom allValuesFrom = (OWLObjectAllValuesFrom) superClass;
                    c3 = allValuesFrom.getFiller();
                    r2 = allValuesFrom.getProperty();
                }
            }
            if (c2 == null || c3 == null || r1 == null || r2 == null) {
                continue;
            }
            boolean disjointFound = false;
            for (OWLDisjointClassesAxiom disjoint : ontology.getAxioms(AxiomType.DISJOINT_CLASSES)) {
                if (disjoint.getClassExpressions().contains(c2) && disjoint.getClassExpressions().contains(c3)) {
                    disjointFound = true;
                    break;
                }
            }
            if (disjointFound) {
                return Optional.of(dataFactory.getOWLSubObjectPropertyOfAxiom(r1, r2));
            }
        }
        return Optional.empty();
    }
    @Override
    public String getName() {
        return "UEWPI";
    }
}
