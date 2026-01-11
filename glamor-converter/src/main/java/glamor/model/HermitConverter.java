package glamor;
import glamor.TripleObj;
import glamor.model.*;

public class HermitConverter implements ModelConverter {

    @Override
    public String convert(TripleObj t) {
        return String.format("%s %s %s", t.s, t.p, t.o);
    }
}

