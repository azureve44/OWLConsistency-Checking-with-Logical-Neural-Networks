package glamor;
import glamor.TripleObj;

public class LNNConverter implements ModelConverter {
    @Override
    public String convert(TripleObj t) {
        String pred = normalizePredicate(t.p);
        String subj = normalize(t.s);
        String obj  = normalize(t.o);

        // Unary
        if (t.p.equals("rdf:type") || t.p.equals("type")) {
            return pred + "(" + subj + ")";
        }

        // Binary
        return pred + "(" + subj + "," + obj + ")";
    }

    private String normalize(String x) {
        return x.replace(" ", "_").replace(":", "");
    }

    private String normalizePredicate(String p) {
        switch (p) {
            case "rdf:type": return "";
            case "subClassOf": return "subClassOf";
            case "EquivalentTo": return "equiv";
            default: return p.replace(":", "_");
        }
    }
}	
