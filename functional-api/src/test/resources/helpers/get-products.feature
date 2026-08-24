Feature: Cliente reutilizable del catálogo

  Scenario:
    Given url baseUrl
    And header X-QE-Run-Id = runId
    And path 'products'
    And params queryParams
    When method get
