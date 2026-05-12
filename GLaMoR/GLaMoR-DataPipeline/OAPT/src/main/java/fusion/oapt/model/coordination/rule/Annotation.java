package fusion.oapt.model.coordination.rule;
import fusion.oapt.model.Constant;
import fusion.oapt.model.coordination.Coordinator;
import org.apache.jena.query.Query;
import org.apache.jena.query.QueryExecution;
import org.apache.jena.query.QueryExecutionFactory;
import org.apache.jena.query.QueryFactory;
import org.apache.jena.query.QuerySolution;
import org.apache.jena.query.ResultSet;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.Property;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.rdf.model.Statement;
import org.apache.jena.rdf.model.StmtIterator;
import org.apache.jena.vocabulary.OWL;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Set;
public class Annotation implements Coordinator
{
    private static final long LOG_EVERY_STATEMENTS = 100000L;
    private ArrayList<Property> annoProperties = new ArrayList<Property>(5);
    public Annotation()
    {
        annoProperties.add(RDFS.comment);
        annoProperties.add(RDFS.label);
        annoProperties.add(RDFS.seeAlso);
        annoProperties.add(RDFS.isDefinedBy);
        annoProperties.add(OWL.versionInfo);
    }
    private void addAnnoProperty(Property p)
    {
        annoProperties.add(p);
    }
    private boolean isRemovedAnnoProperty(Property p)
    {
        if (p.toString().equals(RDFS.label.toString()) ||
                        p.toString().equals(RDFS.comment.toString())) {
            return false;
        }
        if (p.getNameSpace().equals(Constant.DC_NS)) {
            return true;
        }
        for (int i = 0; i < annoProperties.size(); i++) {
            if (annoProperties.get(i).toString().equals(p.toString())) {
                return true;
            }
        }
        return false;
    }
    private boolean isAnnotationPropertyTypeStatement(Statement statement,
                    Set<String> annotationPropertyUris)
    {
        if (statement == null || annotationPropertyUris == null || annotationPropertyUris.isEmpty()) {
            return false;
        }
        if (!RDF.type.equals(statement.getPredicate())) {
            return false;
        }
        if (!OWL.AnnotationProperty.toString().equals(statement.getObject().toString())) {
            return false;
        }
        return annotationPropertyUris.contains(statement.getSubject().toString());
    }
    private void logAnnotationPhase(String phase, String detail)
    {
        System.out.println("[OAPT-DIAG|ANNOTATION_PROGRESS] phase=" + phase
                + (detail != null && detail.length() > 0 ? " " + detail : ""));
    }
    public Model coordinate(Model model)
    {
        final long start = System.currentTimeMillis();
        Annotation anno = new Annotation();
        ArrayList<Statement> retainedStmt = new ArrayList<Statement>();
        Set<String> annotationPropertyUris = new HashSet<String>();
        long initialStatementCount = model != null ? model.size() : -1;
        logAnnotationPhase("enter", "statementCount=" + initialStatementCount);
        String querystr = " PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
                                + " PREFIX owl: <http://www.w3.org/2002/07/owl#> "
                                + " SELECT ?x WHERE {?x rdf:type owl:AnnotationProperty} ";
        Query query = QueryFactory.create(querystr);
        QueryExecution qe = QueryExecutionFactory.create(query, model);
        ResultSet results = qe.execSelect();
        int annotationPropertyCount = 0;
        for (Iterator<?> iter = results; iter.hasNext();) {
            QuerySolution res = (QuerySolution) iter.next();
            Resource x = (Resource) res.get("x");
            annotationPropertyUris.add(x.toString());
            anno.addAnnoProperty(model.getProperty(x.toString()));
            annotationPropertyCount++;
        }
        qe.close();
        logAnnotationPhase("after_annotation_property_query",
                "annotationPropertyCount=" + annotationPropertyCount
                        + " trackedAnnotationProperties=" + annotationPropertyUris.size()
                        + " elapsedMs=" + (System.currentTimeMillis() - start));
        StmtIterator stmts = model.listStatements();
        long scannedStatements = 0;
        long removedMatches = 0;
        while (stmts.hasNext()) {
            Statement s = (Statement) stmts.next();
            scannedStatements++;
            Property p = s.getPredicate();
            boolean removeStatement = isAnnotationPropertyTypeStatement(s, annotationPropertyUris)
                    || anno.isRemovedAnnoProperty(p);
            if (removeStatement) {
                removedMatches++;
            } else {
                retainedStmt.add(s);
            }
            if (scannedStatements % LOG_EVERY_STATEMENTS == 0) {
                logAnnotationPhase("scan_checkpoint",
                        "scannedStatements=" + scannedStatements
                                + " removedMatches=" + removedMatches
                                + " retainedStatements=" + retainedStmt.size()
                                + " elapsedMs=" + (System.currentTimeMillis() - start));
            }
        }
        stmts.close();
        logAnnotationPhase("after_scan",
                "scannedStatements=" + scannedStatements
                        + " removedMatches=" + removedMatches
                        + " retainedStatements=" + retainedStmt.size()
                        + " elapsedMs=" + (System.currentTimeMillis() - start));
        logAnnotationPhase("before_rebuild",
                "retainedStatements=" + retainedStmt.size()
                        + " elapsedMs=" + (System.currentTimeMillis() - start));
        model.removeAll();
        logAnnotationPhase("after_clear_for_rebuild",
                "statementCount=" + model.size()
                        + " elapsedMs=" + (System.currentTimeMillis() - start));
        model.add(retainedStmt);
        logAnnotationPhase("after_rebuild",
                "finalStatementCount=" + model.size()
                        + " elapsedMs=" + (System.currentTimeMillis() - start));
        logAnnotationPhase("exit",
                "removedApplied=" + removedMatches
                        + " initialStatementCount=" + initialStatementCount
                        + " finalStatementCount=" + (model != null ? model.size() : -1)
                        + " elapsedMs=" + (System.currentTimeMillis() - start));
        return model;
    }
}
