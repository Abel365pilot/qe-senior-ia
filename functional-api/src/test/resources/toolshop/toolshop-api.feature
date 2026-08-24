@functional @api
Feature: Criterios de aceptación de Toolshop por API

  Background:
    * url baseUrl
    * configure headers = { Accept: 'application/json', Content-Type: 'application/json' }
    * def loginSuccessSchema = read('classpath:schemas/login-success.json')
    * def loginErrorSchema = read('classpath:schemas/login-error.json')
    * def paginatedProductsSchema = read('classpath:schemas/paginated-products.json')
    * def productSchema = read('classpath:schemas/product.json')
    * def cartSchema = read('classpath:schemas/cart.json')
    * def cartItemSchema = read('classpath:schemas/cart-item.json')

  @positive @authentication
  Scenario: Autenticación con credenciales válidas
    * if (!credentials.email || !credentials.password) karate.fail('Defina TOOLSHOP_USER_EMAIL y TOOLSHOP_USER_PASSWORD')
    * def result = call read('classpath:helpers/login.feature') { email: '#(credentials.email)', password: '#(credentials.password)' }
    * match result.responseStatus == 200
    * match result.response contains loginSuccessSchema
    * match result.response.token_type.toLowerCase() == 'bearer'
    * assert result.response.access_token.length > 20
    * assert result.response.expires_in > 0

  @negative @authentication
  Scenario: Rechazo de credenciales inválidas sin alterar una cuenta compartida
    * def invalidEmail = 'qe-invalid-' + runId + '@example.invalid'
    * def invalidPassword = 'invalid-' + runId
    * def result = call read('classpath:helpers/login.feature') { email: '#(invalidEmail)', password: '#(invalidPassword)' }
    * match result.responseStatus == 401
    * match result.response contains loginErrorSchema

  @positive @catalog
  Scenario: Búsqueda por texto y filtro de productos por categoría
    * def baseParams = { sort: 'price,asc', page: 1 }
    * def catalog = call read('classpath:helpers/get-products.feature') { queryParams: '#(baseParams)' }
    * match catalog.responseStatus == 200
    * match catalog.response contains paginatedProductsSchema
    * assert catalog.response.data.length > 0
    * match each catalog.response.data contains productSchema
    * def seedProduct = catalog.response.data[0]
    * match seedProduct.category == '#object'

    * def searchResult = call read('classpath:helpers/search-products.feature') { query: '#(seedProduct.name)' }
    * match searchResult.responseStatus == 200
    * match searchResult.response contains paginatedProductsSchema
    * assert searchResult.response.data.length > 0
    * match each searchResult.response.data contains productSchema
    * def normalizedQuery = seedProduct.name.toLowerCase()
    * def searchMisses = karate.filter(searchResult.response.data, function(x){ return x.name.toLowerCase().indexOf(normalizedQuery) === -1 })
    * match searchMisses == []

    * def categoryParams = { by_category: '#(seedProduct.category.id)', sort: 'price,asc', page: 1 }
    * def filtered = call read('classpath:helpers/get-products.feature') { queryParams: '#(categoryParams)' }
    * match filtered.responseStatus == 200
    * match filtered.response contains paginatedProductsSchema
    * assert filtered.response.data.length > 0
    * match each filtered.response.data contains productSchema
    * def categoryId = seedProduct.category.id
    * def categoryMisses = karate.filter(filtered.response.data, function(x){ return !x.category || x.category.id !== categoryId })
    * match categoryMisses == []

  @positive @cart @isolated
  Scenario: Carrito aislado refleja cantidad dos y total calculado
    * def catalog = call read('classpath:helpers/get-products.feature') { queryParams: { sort: 'price,asc', page: 1 } }
    * match catalog.responseStatus == 200
    * def candidates = karate.filter(catalog.response.data, function(x){ return x.name !== 'Thor Hammer' })
    * assert candidates.length > 0
    * def product = candidates[0]
    * match product contains productSchema

    * def created = call read('classpath:helpers/create-cart.feature')
    * match created.responseStatus == 201
    * match created.response contains { id: '#string' }
    * def cartId = created.response.id

    * def added = call read('classpath:helpers/add-cart-item.feature') { cartId: '#(cartId)', productId: '#(product.id)', quantity: 2 }
    * match added.responseStatus == 200
    * match added.response contains { result: '#string' }

    * def fetched = call read('classpath:helpers/get-cart.feature') { cartId: '#(cartId)' }
    * def cleanup = call read('classpath:helpers/delete-cart.feature') { cartId: '#(cartId)' }
    * match cleanup.responseStatus == 204
    * match fetched.responseStatus == 200
    * match fetched.response contains cartSchema
    * match each fetched.response.cart_items contains cartItemSchema
    * def selectedItems = karate.filter(fetched.response.cart_items, function(x){ return x.product_id === product.id })
    * match selectedItems == '#[1]'
    * match selectedItems[0].quantity == 2
    * match selectedItems[0].product contains productSchema
    * def CartTotals = Java.type('toolshop.support.CartTotals')
    * def calculatedTotal = CartTotals.total(fetched.response.cart_items, fetched.response.additional_discount_percentage)
    * def expectedTotal = Math.round(product.price * 2 * 100) / 100
    * match calculatedTotal == expectedTotal
