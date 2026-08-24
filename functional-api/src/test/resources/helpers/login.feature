@report=false
Feature: Cliente reutilizable de autenticación

  Scenario:
    Given url baseUrl
    And path 'users', 'login'
    And request { email: '#(email)', password: '#(password)' }
    When method post
