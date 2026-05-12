package smoke;
import fusion.oapt.algorithm.partitioner.SeeCOnt.Findk.FindOptimalCluster;
import fusion.oapt.general.cc.Controller;
import fusion.oapt.general.cc.Coordinator;
import org.apache.jena.ontology.OntModel;
import org.junit.Assert;
import org.junit.Test;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
public class University0SmokeTest {
    @Test
    public void modularizesUniversity0Ontology() throws Exception {
        Path ontology = Paths.get("..", "data", "lubm", "University0_0.owl").toAbsolutePath().normalize();
        Assert.assertTrue("Test ontology not found: " + ontology, Files.exists(ontology));
        Controller controller = new Controller(ontology.toString());
        FindOptimalCluster optimalCluster = new FindOptimalCluster(controller.MB);
        int numCH = optimalCluster.FindOptimalClusterFunc();
        Coordinator.KNumCH = numCH;
        List<OntModel> modules = controller.InitialRun_API("SeeCOnt", Coordinator.KNumCH);
        System.out.println("SMOKE_NUMCH=" + numCH);
        System.out.println("SMOKE_MODULE_COUNT=" + modules.size());
        Assert.assertFalse("No modules generated", modules.isEmpty());
    }
}
