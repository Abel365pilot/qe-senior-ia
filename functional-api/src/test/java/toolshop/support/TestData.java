package toolshop.support;

import java.util.Map;

public final class TestData {

    private TestData() {
    }

    public static Map<String, String> invalidCredentials(String runId) {
        if (runId == null || runId.isBlank()) {
            throw new IllegalArgumentException("runId es obligatorio para generar datos aislados");
        }
        String discriminator = runId.replaceAll("[^A-Za-z0-9-]", "");
        if (discriminator.isBlank()) {
            throw new IllegalArgumentException("runId no contiene caracteres utilizables");
        }
        return Map.of(
                "email", "qe-invalid-" + discriminator + "@example.invalid",
                "password", "invalid-" + discriminator
        );
    }
}
