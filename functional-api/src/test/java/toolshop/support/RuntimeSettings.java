package toolshop.support;

import java.net.URI;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

public final class RuntimeSettings {

    private static final Set<String> SUPPORTED_ENVIRONMENTS = Set.of("local", "public");
    private static final Pattern EMAIL = Pattern.compile("^[^\\s@]+@[^\\s@]+$");
    private static final int MIN_TIMEOUT_MS = 1_000;
    private static final int MAX_TIMEOUT_MS = 60_000;

    private final String environment;
    private final String baseUrl;
    private final String email;
    private final String password;
    private final String runId;
    private final int connectTimeoutMs;
    private final int readTimeoutMs;

    private RuntimeSettings(
            String environment,
            String baseUrl,
            String email,
            String password,
            String runId,
            int connectTimeoutMs,
            int readTimeoutMs
    ) {
        this.environment = environment;
        this.baseUrl = baseUrl;
        this.email = email;
        this.password = password;
        this.runId = runId;
        this.connectTimeoutMs = connectTimeoutMs;
        this.readTimeoutMs = readTimeoutMs;
    }

    public static RuntimeSettings load(String environment) {
        return from(environment, System.getenv());
    }

    static RuntimeSettings from(String requestedEnvironment, Map<String, String> variables) {
        String environment = required(requestedEnvironment, "karate.env").toLowerCase(Locale.ROOT);
        if (!SUPPORTED_ENVIRONMENTS.contains(environment)) {
            throw new IllegalArgumentException("karate.env no soportado: " + environment + ". Use local o public.");
        }

        String email = required(variables.get("TOOLSHOP_USER_EMAIL"), "TOOLSHOP_USER_EMAIL");
        if (!EMAIL.matcher(email).matches()) {
            throw new IllegalArgumentException("TOOLSHOP_USER_EMAIL no tiene formato de email valido");
        }
        String password = requiredSecret(variables.get("TOOLSHOP_USER_PASSWORD"), "TOOLSHOP_USER_PASSWORD");
        String baseUrl = resolveBaseUrl(environment, variables);

        return new RuntimeSettings(
                environment,
                baseUrl,
                email,
                password,
                "qe-" + UUID.randomUUID(),
                boundedInteger(variables, "TOOLSHOP_CONNECT_TIMEOUT_MS", 5_000),
                boundedInteger(variables, "TOOLSHOP_READ_TIMEOUT_MS", 10_000)
        );
    }

    private static String resolveBaseUrl(String environment, Map<String, String> variables) {
        String defaultUrl = environment.equals("local")
                ? "http://localhost:8091"
                : "https://api.practicesoftwaretesting.com";
        String candidate = variables.getOrDefault("TOOLSHOP_BASE_URL", defaultUrl).trim();
        while (candidate.endsWith("/")) {
            candidate = candidate.substring(0, candidate.length() - 1);
        }

        URI uri;
        try {
            uri = URI.create(candidate);
        } catch (IllegalArgumentException exception) {
            throw new IllegalArgumentException("TOOLSHOP_BASE_URL no es una URI valida", exception);
        }
        if (!uri.isAbsolute() || uri.getHost() == null || uri.getUserInfo() != null
                || uri.getQuery() != null || uri.getFragment() != null) {
            throw new IllegalArgumentException("TOOLSHOP_BASE_URL debe ser una URL HTTP(S) absoluta sin credenciales, query ni fragmento");
        }
        if (uri.getPath() != null && !uri.getPath().isBlank()) {
            throw new IllegalArgumentException("TOOLSHOP_BASE_URL no debe incluir una ruta");
        }
        if (!Set.of("http", "https").contains(uri.getScheme().toLowerCase(Locale.ROOT))) {
            throw new IllegalArgumentException("TOOLSHOP_BASE_URL debe usar http o https");
        }

        if (environment.equals("public")) {
            if (!flag(variables, "TOOLSHOP_ALLOW_PUBLIC")) {
                throw new IllegalArgumentException("El entorno public requiere TOOLSHOP_ALLOW_PUBLIC=true como opt-in explicito");
            }
            if (!uri.getScheme().equalsIgnoreCase("https")
                    || !uri.getHost().equalsIgnoreCase("api.practicesoftwaretesting.com")) {
                throw new IllegalArgumentException("El perfil public solo admite el endpoint HTTPS oficial de Toolshop");
            }
        } else if (!isLoopback(uri.getHost()) && !flag(variables, "TOOLSHOP_ALLOW_REMOTE")) {
            throw new IllegalArgumentException("Un host no local requiere TOOLSHOP_ALLOW_REMOTE=true como opt-in explicito");
        }
        return candidate;
    }

    private static boolean isLoopback(String host) {
        return host.equalsIgnoreCase("localhost")
                || host.equals("127.0.0.1")
                || host.equals("::1")
                || host.equals("0:0:0:0:0:0:0:1");
    }

    private static boolean flag(Map<String, String> variables, String key) {
        String raw = variables.get(key);
        if (raw == null || raw.isBlank()) {
            return false;
        }
        if (!raw.equalsIgnoreCase("true") && !raw.equalsIgnoreCase("false")) {
            throw new IllegalArgumentException(key + " debe ser true o false");
        }
        return Boolean.parseBoolean(raw);
    }

    private static int boundedInteger(Map<String, String> variables, String key, int defaultValue) {
        String raw = variables.get(key);
        if (raw == null || raw.isBlank()) {
            return defaultValue;
        }
        int value;
        try {
            value = Integer.parseInt(raw);
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(key + " debe ser un entero", exception);
        }
        if (value < MIN_TIMEOUT_MS || value > MAX_TIMEOUT_MS) {
            throw new IllegalArgumentException(key + " debe estar entre " + MIN_TIMEOUT_MS + " y " + MAX_TIMEOUT_MS);
        }
        return value;
    }

    private static String required(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Falta la configuracion obligatoria " + field);
        }
        return value.trim();
    }

    private static String requiredSecret(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Falta la configuracion obligatoria " + field);
        }
        return value;
    }

    public String environment() {
        return environment;
    }

    public String baseUrl() {
        return baseUrl;
    }

    public String email() {
        return email;
    }

    public String password() {
        return password;
    }

    public String runId() {
        return runId;
    }

    public int connectTimeoutMs() {
        return connectTimeoutMs;
    }

    public int readTimeoutMs() {
        return readTimeoutMs;
    }

    @Override
    public String toString() {
        return "RuntimeSettings[environment=" + environment
                + ", baseUrl=" + baseUrl
                + ", email=<redacted>, password=<redacted>, runId=" + runId
                + ", connectTimeoutMs=" + connectTimeoutMs
                + ", readTimeoutMs=" + readTimeoutMs + "]";
    }
}
