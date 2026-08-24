Feature: Cliente reutilizable de búsqueda

  Scenario:
    Given url baseUrl
    And path 'products', 'search'
    And params { q: '#(query)', page: 1 }
    When method get
