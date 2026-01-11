package glamor;
import glamor.TripleObj;
import glamor.model.*;
public class LINNConverter implements ModelConverter {
    @Override
    public String convert(TripleObj t) {
        String pred = "soft_" + normalizePredicate(t.p);
        String subj = normalize(t.s);
        String obj  = normalize(t.o);

        if (t.p.equals("rdf:type") || t.p.equals("type")) {
            return pred + "(" + subj + ")";
        }

        return pred + "(" + subj + "," + obj + ")";
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
