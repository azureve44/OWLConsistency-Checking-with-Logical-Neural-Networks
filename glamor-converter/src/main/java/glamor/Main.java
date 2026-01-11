package glamor;

import java.nio.file.*;
import java.util.concurrent.*;

public class Main {

    public static void main(String[] args) throws Exception {

        if (args.length < 2) {
            System.out.println("Usage: java -jar glamor-converter.jar <input_dir> <output_dir> [threads]");
            return;
        }

        Path inputDir = Paths.get(args[0]);
        Path outputDir = Paths.get(args[1]);
        int threads = args.length >= 3 ? Integer.parseInt(args[2]) : 8;

        if (!Files.exists(outputDir)) {
            Files.createDirectories(outputDir);
        }

        ExecutorService pool = Executors.newFixedThreadPool(threads);

        try (DirectoryStream<Path> stream = Files.newDirectoryStream(inputDir, "*.jsonl")) {
            for (Path f : stream) {
                pool.submit(new FileProcessor(f, outputDir));
            }
        }

        pool.shutdown();
        pool.awaitTermination(999, TimeUnit.DAYS);

        System.out.println("All files processed.");
    }
}

