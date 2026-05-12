package main;
import fusion.oapt.algorithm.partitioner.SeeCOnt.Findk.FindOptimalCluster;
import fusion.oapt.general.cc.Controller;
import fusion.oapt.general.cc.Coordinator;
import org.apache.jena.ontology.OntModel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
public class BioPortalDiagnosticsMain {
    public static void main(String[] args) throws Exception {
        if (args.length == 0 || args[0].trim().isEmpty()) {
            throw new IllegalArgumentException("Usage: BioPortalDiagnosticsMain <ontology-path>");
        }
        Path ontology = Paths.get(args[0]).toAbsolutePath().normalize();
        if (!Files.exists(ontology)) {
            throw new IllegalArgumentException("Ontology not found: " + ontology);
        }
        Controller.CheckBuildModel = false;
        Controller.MB = null;
        Coordinator.KNumCH = 0;
        Coordinator.clusters = null;
        Coordinator.CH = null;
        long start = System.currentTimeMillis();
        Controller controller = new Controller(ontology.toString());
        FindOptimalCluster optimalCluster = new FindOptimalCluster(controller.MB);
        int numCH = optimalCluster.FindOptimalClusterFunc();
        Coordinator.KNumCH = numCH;
        List<OntModel> modules = controller.InitialRun_API("SeeCOnt", Coordinator.KNumCH);
        long elapsedMillis = System.currentTimeMillis() - start;
        int moduleCount = modules != null ? modules.size() : -1;
        System.out.println("[OAPT-DIAG|TEST_SUMMARY] ontology=" + ontology.getFileName()
                + " chosenK=" + numCH
                + " moduleCount=" + moduleCount
                + " elapsedMs=" + elapsedMillis);
        if (modules == null || modules.isEmpty()) {
            throw new IllegalStateException("No modules generated for " + ontology);
        }
    }
}
