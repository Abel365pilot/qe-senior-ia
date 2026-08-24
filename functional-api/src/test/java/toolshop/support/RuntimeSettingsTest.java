package toolshop.support;

import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RuntimeSettingsTest {

    @Test
    void buildsSafeLocalConfigurationAndNormalizesTrailingSlash() {
        Map<String, String> variables = validCredentials();
        variables.put("TOOLSHOP_BASE_URL", "http://localhost:8091/");
        variables.put("TOOLSHOP_CONNECT_TIMEOUT_MS", "2500");
        variables.put("TOOLSHOP_READ_TIMEOUT_MS", "12000");
        variables.put("TOOLSHOP_USER_PASSWORD", " password-with-significant-spaces ");

        RuntimeSettings settings = RuntimeSettings.from("LOCAL", variables);

        assertEquals("local", settings.environment());
        assertEquals("http://localhost:8091", settings.baseUrl());
        assertEquals(2500, settings.connectTimeoutMs());
        assertEquals(12000, settings.readTimeoutMs());
        assertEquals(" password-with-significant-spaces ", settings.password());
        assertTrue(settings.runId().startsWith("qe-"));
        assertFalse(settings.toString().contains("password-with-significant-spaces"));
    }

    @Test
    void rejectsMissingCredentialsBeforeAnyRequest() {
        Map<String, String> missingPassword = new HashMap<>();
        missingPassword.put("TOOLSHOP_USER_EMAIL", "qa@example.test");

        assertThrows(IllegalArgumentException.class, () -> RuntimeSettings.from("local", missingPassword));
    }

    @Test
    void requiresExplicitOptInForSharedPublicTarget() {
        Map<String, String> variables = validCredentials();

        assertThrows(IllegalArgumentException.class, () -> RuntimeSettings.from("public", variables));

        variables.put("TOOLSHOP_ALLOW_PUBLIC", "true");
        RuntimeSettings settings = RuntimeSettings.from("public", variables);
        assertEquals("https://api.practicesoftwaretesting.com", settings.baseUrl());
    }

    @Test
    void preventsAccidentalRemoteExecutionAndUnsafeUrls() {
        Map<String, String> remote = validCredentials();
        remote.put("TOOLSHOP_BASE_URL", "https://example.com");
        assertThrows(IllegalArgumentException.class, () -> RuntimeSettings.from("local", remote));

        Map<String, String> credentialInUrl = validCredentials();
        String unsafeCredentialUrl = String.join("", "http://user", ":", "secret@localhost:8091");
        credentialInUrl.put("TOOLSHOP_BASE_URL", unsafeCredentialUrl);
        assertThrows(IllegalArgumentException.class, () -> RuntimeSettings.from("local", credentialInUrl));
    }

    @Test
    void rejectsUnsupportedEnvironmentAndOutOfRangeTimeouts() {
        assertThrows(IllegalArgumentException.class, () -> RuntimeSettings.from("staging", validCredentials()));

        Map<String, String> invalidTimeout = validCredentials();
        invalidTimeout.put("TOOLSHOP_READ_TIMEOUT_MS", "999");
        assertThrows(IllegalArgumentException.class, () -> RuntimeSettings.from("local", invalidTimeout));
    }

    private static Map<String, String> validCredentials() {
        Map<String, String> variables = new HashMap<>();
        variables.put("TOOLSHOP_USER_EMAIL", "qa@example.test");
        variables.put("TOOLSHOP_USER_PASSWORD", "valid-password");
        return variables;
    }
}
