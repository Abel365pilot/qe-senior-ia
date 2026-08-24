function fn() {
  var System = Java.type('java.lang.System');
  return {
    baseUrl: System.getenv('TOOLSHOP_BASE_URL') || 'http://localhost:8091'
  };
}
