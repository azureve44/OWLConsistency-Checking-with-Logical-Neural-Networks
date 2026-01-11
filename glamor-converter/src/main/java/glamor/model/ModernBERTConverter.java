package glamor;
import glamor.TripleObj;

public class ModernBERTConverter implements ModelConverter {
    @Override
    public String convert(TripleObj t) {
        return String.format("%s %s %s.", 
            clean(t.s), 
            readable(t.p), 
            clean(t.o));
    }

    private String readable(String p) {
        switch (p) {
            case "rdf:type": return "is a";
            case "is": return "is";
            case "subClassOf": return "is a subclass of";
            case "EquivalentTo": return "is equivalent to";
            default: return p.replace("_", " ");
        }
    }

    private String clean(String x) {
        return x.replace(":", "").replace("_"," ");
    }	
	
}
