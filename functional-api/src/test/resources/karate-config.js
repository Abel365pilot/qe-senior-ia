function fn() {
  var env = karate.env || 'local';
  var RuntimeSettings = Java.type('toolshop.support.RuntimeSettings');
  var settings = RuntimeSettings.load(env);
  var config = {
    environment: settings.environment(),
    baseUrl: settings.baseUrl(),
    runId: settings.runId(),
    credentials: {
      email: settings.email(),
      password: settings.password()
    }
  };

  karate.configure('connectTimeout', settings.connectTimeoutMs());
  karate.configure('readTimeout', settings.readTimeoutMs());
  karate.configure('lowerCaseResponseHeaders', true);
  karate.configure('logPrettyRequest', false);
  karate.configure('logPrettyResponse', false);
  karate.configure('afterScenario', function() {
    var cleanupRequired = karate.get('cleanupRequired', false);
    var cartId = karate.get('cartId');
    if (!cleanupRequired || !cartId) {
      return;
    }
    try {
      var cleanup = karate.call('classpath:helpers/delete-cart.feature', {
        baseUrl: config.baseUrl,
        cartId: cartId,
        runId: config.runId,
        cleanupRequired: false
      });
      karate.log('Limpieza defensiva de carrito', cartId, 'HTTP', cleanup.responseStatus);
    } catch (error) {
      karate.log('No se pudo limpiar el carrito aislado', cartId, 'causa:', String(error));
    }
  });

  return config;
}
