@functional @api
Feature: Criterios de aceptación de Toolshop por API

  Background:
    * url baseUrl
    * configure headers = function(){ return { Accept: 'application/json', 'Content-Type': 'application/json', 'X-QE-Run-Id': runId } }
    * def cleanupRequired = false
    * def cartId = null
    * def loginSuccessSchema = read('classpath:schemas/login-success.json')
    * def loginErrorSchema = read('classpath:schemas/login-error.json')
    * def paginatedProductsSchema = read('classpath:schemas/paginated-products.json')
    * def productSchema = read('classpath:schemas/product.json')
    * def cartSchema = read('classpath:schemas/cart.json')
    * def cartItemSchema = read('classpath:schemas/cart-item.json')

  @positive @authentication
  Scenario: Autenticación con credenciales válidas
    * def loginEmail = credentials.email
    * def loginPassword = credentials.password
    * def result = call read('classpath:helpers/login.feature')
    * match result.responseStatus == 200
    * match result.responseHeaders['content-type'][0] contains 'application/json'
    * match result.response contains loginSuccessSchema

  @negative @authentication
  Scenario: Rechazo de credenciales inválidas sin alterar una cuenta compartida
    * def TestData = Java.type('toolshop.support.TestData')
    * def invalidCredentials = TestData.invalidCredentials(runId)
    * def loginEmail = invalidCredentials.email
    * def loginPassword = invalidCredentials.password
    * def result = call read('classpath:helpers/login.feature')
    * match result.responseStatus == 401
    * match result.responseHeaders['content-type'][0] contains 'application/json'
    * match result.response contains loginErrorSchema

  @positive @catalog
  Scenario: Búsqueda por texto y filtro de productos por categoría
    * def baseParams = { sort: 'price,asc', page: 1 }
    * def catalog = call read('classpath:helpers/get-products.feature') { queryParams: '#(baseParams)' }
    * match catalog.responseStatus == 200
    * match catalog.responseHeaders['content-type'][0] contains 'application/json'
    * match catalog.response contains paginatedProductsSchema
    * match catalog.response.current_page == 1
    * assert catalog.response.data.length > 0
    * match each catalog.response.data contains productSchema
    * assert catalog.response.total >= catalog.response.data.length
    * def eligibleSeeds = karate.filter(catalog.response.data, function(x){ return !!(x.category && x.category.id && x.name) })
    * assert eligibleSeeds.length > 0
    * def seedProduct = eligibleSeeds[0]

    * def searchResult = call read('classpath:helpers/search-products.feature') { query: '#(seedProduct.name)' }
    * match searchResult.responseStatus == 200
    * match searchResult.responseHeaders['content-type'][0] contains 'application/json'
    * match searchResult.response contains paginatedProductsSchema
    * assert searchResult.response.data.length > 0
    * match each searchResult.response.data contains productSchema
    * def normalizedQuery = seedProduct.name.toLowerCase()
    * def searchMisses = karate.filter(searchResult.response.data, function(x){ return x.name.toLowerCase().indexOf(normalizedQuery) === -1 })
    * match searchMisses == []

    * def categoryParams = { by_category: '#(seedProduct.category.id)', sort: 'price,asc', page: 1 }
    * def filtered = call read('classpath:helpers/get-products.feature') { queryParams: '#(categoryParams)' }
    * match filtered.responseStatus == 200
    * match filtered.responseHeaders['content-type'][0] contains 'application/json'
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
    * match catalog.responseHeaders['content-type'][0] contains 'application/json'
    * def candidates = karate.filter(catalog.response.data, function(x){ return x.name !== 'Thor Hammer' && !x.is_rental && (x.in_stock === true || x.in_stock >= 2) })
    * assert candidates.length > 0
    * def product = candidates[0]
    * match product contains productSchema

    * def created = call read('classpath:helpers/create-cart.feature')
    * match created.responseStatus == 201
    * match created.responseHeaders['content-type'][0] contains 'application/json'
    * match created.response contains { id: '#string' }
    * def cartId = created.response.id
    * def cleanupRequired = true

    * def added = call read('classpath:helpers/add-cart-item.feature') { cartId: '#(cartId)', productId: '#(product.id)', quantity: 2, cleanupRequired: false }
    * match added.responseStatus == 200
    * match added.responseHeaders['content-type'][0] contains 'application/json'
    * match added.response contains { result: '#string' }

    * def fetched = call read('classpath:helpers/get-cart.feature') { cartId: '#(cartId)', cleanupRequired: false }
    * def cleanup = call read('classpath:helpers/delete-cart.feature') { cartId: '#(cartId)', cleanupRequired: false }
    * def cleanupRequired = false
    * match cleanup.responseStatus == 204
    * match fetched.responseStatus == 200
    * match fetched.responseHeaders['content-type'][0] contains 'application/json'
    * match fetched.response contains cartSchema
    * match fetched.response.id == cartId
    * match each fetched.response.cart_items contains cartItemSchema
    * match fetched.response.cart_items == '#[1]'
    * def selectedItems = karate.filter(fetched.response.cart_items, function(x){ return x.product_id === product.id })
    * match selectedItems == '#[1]'
    * match selectedItems[0].cart_id == cartId
    * match selectedItems[0].quantity == 2
    * match selectedItems[0].product contains productSchema
    * match selectedItems[0].product.price == product.price
    * def CartTotals = Java.type('toolshop.support.CartTotals')
    * def calculatedTotal = CartTotals.total(fetched.response.cart_items, fetched.response.additional_discount_percentage)
    * def itemDiscount = selectedItems[0].discount_percentage || 0
    * def cartDiscount = fetched.response.additional_discount_percentage || 0
    * def expectedTotal = Math.round(product.price * 2 * (1 - itemDiscount / 100) * (1 - cartDiscount / 100) * 100) / 100
    * match calculatedTotal == expectedTotal
