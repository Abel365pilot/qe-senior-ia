package toolshop;

import com.intuit.karate.JsonUtils;
import com.intuit.karate.Results;
import com.intuit.karate.Runner;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ToolshopApiRunner {

    private static final Path REPORT_DIRECTORY = Path.of("target", "karate-reports");

    @Test
    void toolshopAcceptanceCriteria() throws IOException {
        String environment = System.getProperty("karate.env", "local");
        int threads = configuredThreads();

        Results results = Runner.path("classpath:toolshop/toolshop-api.feature")
                .karateEnv(environment)
                .reportDir(REPORT_DIRECTORY.toString())
                .backupReportDir(false)
                .outputHtmlReport(true)
                .outputCucumberJson(true)
                .outputJunitXml(true)
                .failWhenNoScenariosFound(true)
                .parallel(threads);

        writeMachineReadableSummary(results);
        assertEquals(0, results.getFailCount(), results.getErrorMessages());
    }

    private static int configuredThreads() {
        int threads = Integer.getInteger("karate.threads", 1);
        if (threads < 1 || threads > 4) {
            throw new IllegalArgumentException("karate.threads debe estar entre 1 y 4");
        }
        return threads;
    }

    private static void writeMachineReadableSummary(Results results) throws IOException {
        Files.createDirectories(REPORT_DIRECTORY);
        Files.writeString(
                REPORT_DIRECTORY.resolve("karate-summary.json"),
                JsonUtils.toJson(results.toKarateJson(), true),
                StandardCharsets.UTF_8
        );
    }
}
