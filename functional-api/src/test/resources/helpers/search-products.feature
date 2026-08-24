Feature: Cliente reutilizable de búsqueda

  Scenario:
    Given url baseUrl
    And header X-QE-Run-Id = runId
    And path 'products', 'search'
    And params { q: '#(query)', page: 1 }
    When method get
