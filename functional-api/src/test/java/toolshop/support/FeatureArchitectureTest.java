package toolshop.support;

import com.intuit.karate.JsonUtils;
import com.intuit.karate.core.Feature;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FeatureArchitectureTest {

    private static final String MAIN_FEATURE = "toolshop/toolshop-api.feature";
    private static final List<String> HELPERS = List.of(
            "helpers/add-cart-item.feature",
            "helpers/create-cart.feature",
            "helpers/delete-cart.feature",
            "helpers/get-cart.feature",
            "helpers/get-products.feature",
            "helpers/login.feature",
            "helpers/search-products.feature"
    );
    private static final List<String> SCHEMAS = List.of(
            "schemas/cart-item.json",
            "schemas/cart.json",
            "schemas/login-error.json",
            "schemas/login-success.json",
            "schemas/paginated-products.json",
            "schemas/product.json"
    );

    @Test
    void keepsExactlyFourBusinessScenariosWithPositiveAndNegativeCoverage() {
        Feature feature = Feature.read("classpath:" + MAIN_FEATURE);

        assertEquals(4, feature.getSections().size(), "El reto limita el track API a 3 o 4 escenarios");
        Set<String> names = feature.getSections().stream()
                .map(section -> section.getScenario().getName())
                .collect(java.util.stream.Collectors.toSet());
        assertTrue(names.stream().anyMatch(name -> name.contains("credenciales válidas")));
        assertTrue(names.stream().anyMatch(name -> name.contains("credenciales inválidas")));
        assertTrue(names.stream().anyMatch(name -> name.contains("Búsqueda")));
        assertTrue(names.stream().anyMatch(name -> name.contains("Carrito")));
    }

    @Test
    void parsesEveryReusableFeatureAndInvokesAllClientsViaCall() throws IOException {
        HELPERS.forEach(helper -> {
            Feature parsed = Feature.read("classpath:" + helper);
            assertEquals(1, parsed.getSections().size(), helper);
        });

        String source = resourceText(MAIN_FEATURE);
        Matcher matcher = Pattern.compile("classpath:(helpers/[^']+\\.feature)").matcher(source);
        Set<String> invoked = new java.util.HashSet<>();
        while (matcher.find()) {
            invoked.add(matcher.group(1));
        }
        assertEquals(Set.copyOf(HELPERS), invoked);
    }

    @Test
    void validatesAllContractSchemasAsStrictJson() throws IOException {
        for (String schema : SCHEMAS) {
            assertNotNull(JsonUtils.fromJsonStrict(resourceText(schema)), schema);
        }
    }

    @Test
    void forbidsBlindRetriesAndFixedSleepsInBusinessSpecification() throws IOException {
        String source = resourceText(MAIN_FEATURE).toLowerCase();
        assertFalse(source.contains("retry until"));
        assertFalse(source.contains("karate.retry"));
        assertFalse(source.contains("thread.sleep"));
        assertFalse(source.contains("waitfortimeout"));
    }

    private static String resourceText(String resource) throws IOException {
        try (InputStream input = FeatureArchitectureTest.class.getClassLoader().getResourceAsStream(resource)) {
            assertNotNull(input, resource);
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
