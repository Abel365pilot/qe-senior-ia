package toolshop;

import com.intuit.karate.junit5.Karate;

class ToolshopApiRunner {

    @Karate.Test
    Karate toolshopAcceptanceCriteria() {
        return Karate.run("classpath:toolshop/toolshop-api.feature");
    }
}
