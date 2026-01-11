package glamor;
import glamor.TripleObj;
import glamor.model.*;

public class LTNConverter implements ModelConverter {
    @Override
    public String convert(TripleObj t) {
        String pred = normalizePredicate(t.p);
        String subj = normalize(t.s);
        String obj  = normalize(t.o);

        if (t.p.equals("rdf:type")) {
            return pred + "(" + subj + ") = 1.0";
        }

        return pred + "(" + subj + "," + obj + ") = 1.0";
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
