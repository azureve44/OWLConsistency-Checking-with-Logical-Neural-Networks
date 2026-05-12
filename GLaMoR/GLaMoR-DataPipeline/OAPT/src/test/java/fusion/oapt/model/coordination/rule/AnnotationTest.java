package fusion.oapt.model.coordination.rule;
import fusion.oapt.model.Constant;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.Property;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.vocabulary.OWL;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.junit.Assert;
import org.junit.Test;
public class AnnotationTest {
    @Test
    public void keepsLabelAndCommentWhileRemovingAnnotationStatements() {
        Model model = ModelFactory.createDefaultModel();
        Resource subject = model.createResource("urn:test:subject");
        Resource target = model.createResource("urn:test:target");
        Property dcTitle = model.createProperty(Constant.DC_NS, "title");
        Property customAnnotation = model.createProperty("urn:test:customAnnotation");
        model.add(customAnnotation, RDF.type, OWL.AnnotationProperty);
        model.add(subject, RDFS.label, "label");
        model.add(subject, RDFS.comment, "comment");
        model.add(subject, RDFS.seeAlso, target);
        model.add(subject, OWL.versionInfo, "1.0");
        model.add(subject, dcTitle, "dc-value");
        model.add(subject, customAnnotation, "custom-value");
        model.add(subject, RDF.type, OWL.Class);
        new Annotation().coordinate(model);
        Assert.assertTrue(model.contains(subject, RDFS.label, "label"));
        Assert.assertTrue(model.contains(subject, RDFS.comment, "comment"));
        Assert.assertTrue(model.contains(subject, RDF.type, OWL.Class));
        Assert.assertFalse(model.contains(subject, RDFS.seeAlso, target));
        Assert.assertFalse(model.contains(subject, OWL.versionInfo, "1.0"));
        Assert.assertFalse(model.contains(subject, dcTitle, "dc-value"));
        Assert.assertFalse(model.contains(subject, customAnnotation, "custom-value"));
        Assert.assertFalse(model.contains(customAnnotation, RDF.type, OWL.AnnotationProperty));
    }
}
