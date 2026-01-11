package glamor;
import glamor.TripleObj;
import java.util.ArrayList;
import java.util.List;

public class NLMConverter implements ModelConverter {
    @Override
    public String convert(TripleObj t) {
        String pred = normalizePredicate(t.p);
        String subj = normalize(t.s);
        String obj  = normalize(t.o);

        // Unary
        if (t.p.equals("rdf:type") || t.p.equals("type")) {
            return "UNARY " + pred + " " + subj;
        }

        // Binary
        return "BINARY " + pred + " " + subj + " " + obj;
    }

    private String normalize(String x) {
        return x.replace(" ", "_").replace(":", "");
    }

    private String normalizePredicate(String p) {
        switch (p) {
            case "rdf:type": return "isA";
            case "subClassOf": return "subClassOf";
            case "EquivalentTo": return "equiv";
            default: return p.replace(":", "_");
        }
    }	
}
