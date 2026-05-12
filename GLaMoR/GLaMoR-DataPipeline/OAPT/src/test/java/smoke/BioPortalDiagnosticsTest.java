package smoke;
import fusion.oapt.algorithm.partitioner.SeeCOnt.Findk.FindOptimalCluster;
import fusion.oapt.general.cc.Controller;
import fusion.oapt.general.cc.Coordinator;
import org.apache.jena.ontology.OntModel;
import org.junit.Assert;
import org.junit.Before;
import org.junit.Test;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
public class BioPortalDiagnosticsTest {
    private static final Path ONTOLOGY_DIR = Paths.get(
            System.getProperty("oapt.bioportal.dir",
                    "/media/nvme7n1/lniederberger/jm/GLaMoR/data/ontologies"))
            .toAbsolutePath().normalize();
    @Before
    public void resetStaticState() {
        Controller.CheckBuildModel = false;
        Controller.MB = null;
        Coordinator.KNumCH = 0;
        Coordinator.clusters = null;
        Coordinator.CH = null;
    }
    @Test
    public void runsVO() throws Exception {
        runOntology("VO.owl");
    }
    @Test
    public void runsHP() throws Exception {
        runOntology("HP.owl");
    }
    @Test
    public void runsDOID() throws Exception {
        runOntology("DOID.owl");
    }
    @Test
    public void runsCLO() throws Exception {
        runOntology("CLO.owl");
    }
    private void runOntology(String fileName) throws Exception {
        Path ontology = ONTOLOGY_DIR.resolve(fileName).toAbsolutePath().normalize();
        Assert.assertTrue("Test ontology not found: " + ontology, Files.exists(ontology));
        long start = System.currentTimeMillis();
        Controller controller = new Controller(ontology.toString());
        FindOptimalCluster optimalCluster = new FindOptimalCluster(controller.MB);
        int numCH = optimalCluster.FindOptimalClusterFunc();
        Coordinator.KNumCH = numCH;
        List<OntModel> modules = controller.InitialRun_API("SeeCOnt", Coordinator.KNumCH);
        long elapsedMillis = System.currentTimeMillis() - start;
        Assert.assertNotNull("Modules list is null for " + fileName, modules);
        Assert.assertFalse("No modules generated for " + fileName, modules.isEmpty());
        System.out.println("[OAPT-DIAG|TEST_SUMMARY] ontology=" + fileName
                + " chosenK=" + numCH
                + " moduleCount=" + modules.size()
                + " elapsedMs=" + elapsedMillis);
    }
}
