package com.psyagent;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class PsyAgentApplication {

    public static void main(String[] args) {
        SpringApplication.run(PsyAgentApplication.class, args);
    }
}
