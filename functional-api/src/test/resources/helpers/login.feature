@report=false
Feature: Cliente reutilizable de autenticación

  Scenario:
    Given url baseUrl
    And header X-QE-Run-Id = runId
    And path 'users', 'login'
    And request { email: '#(loginEmail)', password: '#(loginPassword)' }
    When method post
