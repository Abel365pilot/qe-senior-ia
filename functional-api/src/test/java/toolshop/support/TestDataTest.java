package toolshop.support;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TestDataTest {

    @Test
    void generatesUniqueNonDeliverableCredentialsPerRun() {
        var first = TestData.invalidCredentials("qe-run-1");
        var second = TestData.invalidCredentials("qe-run-2");

        assertNotEquals(first, second);
        assertTrue(first.get("email").endsWith("@example.invalid"));
        assertTrue(first.get("password").contains("qe-run-1"));
    }

    @Test
    void refusesUntraceableRunIdentifiers() {
        assertThrows(IllegalArgumentException.class, () -> TestData.invalidCredentials("   "));
        assertThrows(IllegalArgumentException.class, () -> TestData.invalidCredentials("###"));
    }
}
