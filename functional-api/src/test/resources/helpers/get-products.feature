Feature: Cliente reutilizable del catálogo

  Scenario:
    Given url baseUrl
    And path 'products'
    And params queryParams
    When method get
