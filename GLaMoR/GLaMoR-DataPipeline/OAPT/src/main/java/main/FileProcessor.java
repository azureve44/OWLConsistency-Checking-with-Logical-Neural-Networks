package main;

import fusion.oapt.algorithm.partitioner.SeeCOnt.Findk.FindOptimalCluster;
import fusion.oapt.algorithm.partitioner.SeeCOnt.ModuleEvaluation;
import fusion.oapt.general.analysis.GeneralAnalysis;
import fusion.oapt.general.cc.Controller;
import fusion.oapt.general.cc.Coordinator;
import org.apache.jena.ontology.OntModel;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;

public class FileProcessor implements Callable<String> {

    private final File file;
    private ModuleEvaluation moduleEvaluation;
    private ArrayList<OntModel> models = new ArrayList<>();
    public FileProcessor(File file, ModuleEvaluation moduleEvaluation){
        this.file = file;
        this.moduleEvaluation = moduleEvaluation;
    }
    @Override
    public String call() throws Exception {
        String result = processFile(this.file);
        return result;
    }

    private String processFile(File file){
        String path = file.getPath();
        System.out.println("Processing the file:\t" + path);
        double start = System.currentTimeMillis();
        Controller con = new Controller(path);
        models.add(con.getOntModel());
        FindOptimalCluster OP = new FindOptimalCluster(Controller.MB);
        int numCH = OP.FindOptimalClusterFunc();
        Coordinator.KNumCH = numCH;
        con.InitialRun_API("SeeCOnt", Coordinator.KNumCH);
        double end = (System.currentTimeMillis() - start) * .001;
        ModuleEvaluation moduleEvaluation = new ModuleEvaluation(con.getModelBuild(), con.getClusters());
        moduleEvaluation.Eval_SeeCont();
        return "\n" + file.getName() + "," + numCH + "," + end + "," + moduleEvaluation.getHoMO() + "," + moduleEvaluation.getHEMo() + "," + moduleEvaluation.getRS();
    }

    public void modularize(List<File> filesInFolder) throws IOException
    {
        GeneralAnalysis GA;
        String content = "Ontology,No. calss,No. of total class ,No. of sub ,No. of Prop,"+",No. of object Pro. ,,No. of data prop";
        File file = new File("src/resources/results/analysis.csv");
        File pfile=file.getParentFile();
        if(!pfile.exists())
        {
            pfile.mkdir();
        }
        FileWriter fw = new FileWriter(file.getAbsoluteFile());
        BufferedWriter bw = new BufferedWriter(fw);
        bw.write(content);

        for(int i=0;i<models.size();i++)
        {
            File f=filesInFolder.get(i);
            OntModel om=models.get(i);
            GA=new GeneralAnalysis(om);
            GA.computeStatics();
            content="\n"+f.getName()+","+GA.getNumClass()+","+GA.getTotnumClass()+","+GA.getNumClass()+","+GA.getNumProp()+","+GA.getNumObectPro()+","+GA.getNumDataPro();
            bw.write(content);
        }
        bw.close();
    }



    public OntModel getOntModel1()
    {
        return models.get(0);
    }


}
