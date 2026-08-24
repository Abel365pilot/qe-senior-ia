function fn() {
  var env = karate.env || 'local';
  var allowedEnvironments = ['local', 'public'];
  if (allowedEnvironments.indexOf(env) === -1) {
    throw new Error('karate.env no soportado: ' + env + '. Use local o public.');
  }

  var System = Java.type('java.lang.System');
  var runId = Java.type('java.util.UUID').randomUUID().toString();
  var email = System.getenv('TOOLSHOP_USER_EMAIL');
  var password = System.getenv('TOOLSHOP_USER_PASSWORD');

  karate.configure('connectTimeout', 5000);
  karate.configure('readTimeout', 10000);
  karate.configure('logPrettyRequest', false);
  karate.configure('logPrettyResponse', false);

  return {
    environment: env,
    runId: runId,
    credentials: {
      email: email || '',
      password: password || ''
    }
  };
}
