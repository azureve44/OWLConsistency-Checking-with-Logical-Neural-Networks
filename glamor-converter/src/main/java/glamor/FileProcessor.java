package glamor;

import com.fasterxml.jackson.databind.ObjectMapper;
import glamor.model.*;
import java.io.*;
import java.nio.file.*;

public class FileProcessor implements Runnable {

    private final Path inputFile;
    private final Path outputDir;
    private final ObjectMapper mapper = new ObjectMapper();

    private final ModelConverter[] converters = new ModelConverter[] {
            new LINNConverter(),
            new NLMConverter(),
            new LTNConverter(),
            new ModernBERTConverter(),
            new HermitConverter()
    };

    private final String[] converterNames = {
            "linn",
            "nlm",
            "ltn",
            "modernbert",
            "hermit"
    };

    public FileProcessor(Path inputFile, Path outputDir) {
        this.inputFile = inputFile;
        this.outputDir = outputDir;
    }

    @Override
    public void run() {
        try {
            String[][] rawTriples = mapper.readValue(inputFile.toFile(), String[][].class);
            long totalLines = rawTriples.length;

            ProgressBar bar = new ProgressBar(totalLines);

            // Writer for all converters
            BufferedWriter[] writers = new BufferedWriter[converters.length];
            for (int i = 0; i < converters.length; i++) {
                Path out = outputDir.resolve(
                        converterNames[i] + "/" + inputFile.getFileName().toString() + ".txt"
                );
                Files.createDirectories(out.getParent());
                writers[i] = Files.newBufferedWriter(out);
            }

            long count = 0;

            for (String[] t : rawTriples) {
                // skip invalid triples
                if (t == null || t.length != 3) {
                    System.err.println("Skipping malformed entry in " + inputFile);
                    continue;
                }

                // TripleObj bauen
                TripleObj triple = new TripleObj(
                        t[0].trim(),
                        t[1].trim(),
                        t[2].trim()
                );

                // Alle Converter durchlaufen
                for (int i = 0; i < converters.length; i++) {
                    String outLine = converters[i].convert(triple);
                    writers[i].write(outLine + "\n");
                }

                bar.update(++count);
            }

            for (var w : writers) w.close();

            System.out.println("\nFinished: " + inputFile.getFileName());

        } catch (Exception e) {
            System.err.println("Error in file " + inputFile + ": " + e.getMessage());
            e.printStackTrace();
        }
    }
}
