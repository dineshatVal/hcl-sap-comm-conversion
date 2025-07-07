import datetime
import os
from google.generativeai import GenerativeModel
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
#model = GenerativeModel('gemini-1.5-flash') # Or 'gemini-1.5-pro' for more complex tasks
model = GenerativeModel('gemini-2.5-pro')

INPUT_HCL_CODE_DIR = 'input'
INPUT_FLOW_DESCRIPTIONS_DIR = 'input/flow_descriptions'
INPUT_SAP_EXAMPLES_DIR = 'input/sap_commerce_examples' # Optional
OUTPUT_SAP_CODE_DIR = 'output'
OUTPUT_CONVERSION_LOGS_DIR = 'output/logs'

PROMPT_FILE_PATH = 'prompts/sap_commerce_conversion_prompt.txt' # Define the path to your prompt file


# Ensure output directories exist
os.makedirs(OUTPUT_SAP_CODE_DIR, exist_ok=True)
os.makedirs(OUTPUT_CONVERSION_LOGS_DIR, exist_ok=True)

def read_file_content(filepath):
    """Reads the content of a given file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None

def write_file_content(filepath, content):
    """Writes content to a given file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully wrote to {filepath}")
    except Exception as e:
        print(f"Error writing to file {filepath}: {e}")

def load_prompt_template(filepath):
    """Loads the prompt template from a file."""
    template = read_file_content(filepath)
    if template is None:
        raise FileNotFoundError(f"Prompt template file not found or empty: {filepath}")
    return template

# Load the prompt template once when the script starts
try:
    GLOBAL_PROMPT_TEMPLATE = load_prompt_template(PROMPT_FILE_PATH)
except FileNotFoundError as e:
    print(f"Critical error: {e}")
    exit(1)


def generate_conversion_prompt(hcl_code_content, flow_description, sap_examples=None, filename=""):
    """
    Constructs the prompt for Gemini Code Assist, refined for SAP Commerce best practices.
    """
    prompt = f"""
    You are an expert in HCL Commerce and SAP Commerce (Hybris) development.
    Your task is to convert the provided HCL Commerce code for a specific feature into
    idiomatic and compliant SAP Commerce Cloud code. Focus on adhering strictly to
    SAP Commerce framework best practices, architectural patterns, and naming conventions.

    **Current Date and Time (for context):** {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z%z")}
    **Current Location:** Bengaluru, Karnataka, India

    **Context:**
    I am providing you with HCL Commerce code for a specific feature and a text description of its functional flow.
    Your goal is to understand the HCL code's purpose within this flow and then re-implement it
    using SAP Commerce principles, primarily focusing on the Service Layer, DAO Layer, Facade Layer,
    and Spring MVC Controllers.

    **HCL Commerce Code (from file: {filename}):**
    ```hcl
    {hcl_code_content}
    ```

    **Feature Flow Description:**
    ```text
    {flow_description}
    ```
    """

    if sap_examples:
        prompt += f"""
        **SAP Commerce Framework Examples/Best Practices (for reference):**
        (These examples demonstrate how SAP Commerce components are typically structured. Please adhere to these patterns.
        They might include sample `items.xml`, service/DAO/controller implementations, or Spring configurations.)
        ```sap_commerce_examples
        {sap_examples}
        ```
        """

    prompt += """
    **SAP Commerce Cloud Best Practices and Requirements (Strict Adherence Required):**

    1.  **Extension Structure:** Assume the converted code will reside within a custom SAP Commerce extension.
        * Core Logic (Services, DAOs, Models): `myextension/src/myextension/core/...`
        * Web Logic (Controllers, DTOs, JSP/Thymeleaf): `myextension/web/src/myextension/cockpits` (for backoffice/cockpits) or `myextension/web/src/myextension/acceleratoraddon/web/controllers/` (for storefront).
        * Resources (Spring, ImpEx, Items.xml): `myextension/resources/...`

    2.  **Layered Architecture (Crucial):**
        * **Service Layer:** Business logic. Should interact with DAOs and other services, *not directly with models for persistence*.
            * Interfaces: End with `Service` (e.g., `MyFeatureService`).
            * Implementations: Start with `Default` and end with `Service` (e.g., `DefaultMyFeatureService`).
            * Methods: Focus on business operations. Throw `ServiceException` for business errors.
        * **DAO Layer:** Data access operations (FlexibleSearch, Jalo queries - prefer FlexibleSearch).
            * Interfaces: End with `DAO` (e.g., `MyFeatureDAO`).
            * Implementations: Start with `Default` and end with `DAO` (e.g., `DefaultMyFeatureDAO`).
            * Methods: Named like `findByX` or `getById`. Should return `null` or empty collections for no results (never throw exceptions for "not found").
        * **Facade Layer (if exposed to frontend/OCC):** Translates between DTOs (Data Transfer Objects) and Models.
            * Interfaces: End with `Facade` (e.g., `MyFeatureFacade`).
            * Implementations: Start with `Default` and end with `Facade` (e.e. `DefaultMyFeatureFacade`).
            * Use Orika mappers or custom converters for DTO-Model conversions.
        * **Controllers (Spring MVC):** Handle web requests, interact with Facades or Services.
            * Annotated with `@Controller` or `@RestController`.
            * Follow Spring MVC conventions (`@RequestMapping`, `@GetMapping`, `@PostMapping`).
            * Return appropriate Spring `View` objects or DTOs for REST endpoints.

    3.  **Data Model (`items.xml`):**
        * **Custom Item Types:** Define new item types (e.g., `<item type="MyCustomItem" extends="GenericItem" autocreate="true" generate="true" ...>`).
            * Prefix custom item types with your project/extension name (e.g., `MyProjectMyCustomItem`).
            * Define a `deployment` table for all non-abstract custom items (e.g., `<deployment table="MyCustomItems" typecode="12345"/>`). Ensure typecode is > 10000.
            * Ensure `autocreate="true"` and `generate="true"` for new types.
            * Use `optional="false"` and `initial="true"` for mandatory attributes.
            * Define `unique="true"` where appropriate, especially for catalog-aware items along with `catalogVersion`.
        * **Attributes:** Define attributes with appropriate types (`java.lang.String`, `java.lang.Integer`, `java.util.Date`, `boolean`, custom enums).
        * **Relations:** Use `<relation>` tags for relationships between item types (`one-to-many`, `many-to-many`). Define deployment tables for many-to-many relations.
        * **Enums:** Define custom enumerations using `<enumtype>`.
        * **Avoid Jalo Customization:** Do not generate or modify Jalo classes directly. Always work with the Service Layer and Models.

    4.  **Spring Configuration (`*-spring.xml`):**
        * Define all Services, DAOs, Facades, and Controllers as Spring beans.
        * Use constructor injection or `@Autowired` for dependencies.
        * Import other Spring configuration files using `<import resource="..." />`.
        * Follow bean naming conventions (e.g., `<bean id="defaultMyFeatureService" class="com.myproject.myextension.core.service.impl.DefaultMyFeatureService">`).

    5.  **Logging:** Use SLF4j/Log4j for logging (e.g., `private static final Logger LOG = LoggerFactory.getLogger(DefaultMyFeatureService.class);`).

    6.  **Error Handling:**
        * Catch specific exceptions and wrap them in custom `ServiceException` or `IntegrationException` as needed.
        * Provide meaningful error messages.

    7.  **ImpEx (for initial data/configuration):**
        * If the HCL Commerce feature involved data setup or configuration, consider how this would be migrated to ImpEx scripts.
        * Generate ImpEx for `items.xml` definitions (essential for creating type instances).
        * Suggest ImpEx for initial master data if applicable.

    8.  **Security (Basic):**
        * Avoid direct SQL injection (use FlexibleSearch parameters).
        * Consider Hybris security annotations for controllers if applicable (`@Secured`).

    9.  **Naming Conventions:**
        * Extension names: All lowercase, descriptive.
        * Java packages: Follow standard Java conventions (`com.mycompany.myextension.core.service.impl`).
        * Class names: PascalCase (`MyFeatureService`, `DefaultMyFeatureDAO`).
        * Method names: camelCase (`findById`, `createFeature`).
        * Spring bean IDs: camelCase (`defaultMyFeatureService`).

    10. **Testability:**
        * Encourage writing clean, testable code. Suggest basic JUnit structure for services/DAOs.

    **Conversion Instructions (reiterated and refined):**

    1.  **Analyze and Map:** Carefully analyze the HCL Commerce code and the feature flow. Map each HCL component (servlet, command, utility, EJB) to its most appropriate SAP Commerce equivalent (Controller, Facade, Service, DAO, Model).
    2.  **Generate Layered Code:** Produce separate Java files for Services (interfaces and implementations), DAOs (interfaces and implementations), Facades (if applicable), and Spring MVC Controllers.
    3.  **Define Items.xml:** Create or extend the `items.xml` file to represent any custom data models required by the feature, adhering to the best practices above.
    4.  **Configure Spring Beans:** Provide the necessary Spring XML configuration (`-spring.xml` files) to wire up all the new components as beans.
    5.  **Generate ImpEx (if data creation is part of the flow):** If the HCL code involved creating specific data instances, generate sample ImpEx for those.
    6.  **Add Explanatory Comments:** Include comments in the generated code explaining the conversion logic, design choices, and any assumptions made. Highlight areas that might require manual review or further refinement.
    7.  **Prioritize Standard Hybris APIs:** Whenever possible, use out-of-the-box SAP Commerce services and APIs (e.g., `modelService`, `flexibleSearchService`, `userService`, `cartService`, etc.) instead of re-implementing common functionality.

    **Output Format:**
    Provide the converted SAP Commerce code for each generated file. Each file should be clearly separated using the delimiter `--- FILE: <suggested/relative/path/from/extension/root> ---`.

    **Example Output Format (continue your response using this structure for all generated files):**

    --- FILE: myextension/extensioninfo.xml ---
    ```xml
    <extension name='myextension' ...>
        <requires-extension name='acceleratorstorefrontcommons'/>
        <requires-extension name='commercefacades'/>
        <coremodule generated='true' manager='de.myproject.myextension.core.jalo.MyextensionManager'
                    packageroot='de.myproject.myextension.core'/>
        <webmodule webroot='/myextensionweb' uiwebroot='/myextensionweb'/>
    </extension>
    ```

    --- FILE: myextension/resources/myextension-items.xml ---
    ```xml
    <?xml version="1.0" encoding="ISO-8859-1"?>
    <items xmlns:xsi="[http://www.w3.org/2001/XMLSchema-instance](http://www.w3.org/2001/XMLSchema-instance)" xsi:noNamespaceSchemaLocation="items.xsd">

        <collectiontypes>
            <collectiontype code="MyCustomStringList" elementtype="java.lang.String" autocreate="true" generate="true"/>
        </collectiontypes>

        <itemtypes>
            <item type="MyProjectFeatureData" extends="GenericItem" autocreate="true" generate="true">
                <deployment table="MyProjectFeatureData" typecode="12345"/> <attributes>
                    <attribute qualifier="featureId" type="java.lang.String" unique="true">
                        <description>Unique identifier for the feature data.</description>
                        <modifiers optional="false" initial="true"/>
                    </attribute>
                    <attribute qualifier="status" type="MyProjectFeatureStatus" autocreate="true">
                        <description>Current status of the feature.</description>
                        <modifiers optional="false"/>
                    </attribute>
                    </attributes>
            </item>
        </itemtypes>

        <enumtypes>
            <enumtype code="MyProjectFeatureStatus" autocreate="true" generate="true">
                <description>Status for MyProjectFeatureData</description>
                <value code="PENDING"/>
                <value code="PROCESSED"/>
                <value code="FAILED"/>
            </enumtype>
        </enumtypes>

        <relations>
            <relation code="MyProjectUserToFeatureDataRelation" localized="false" autocreate="true" generate="true">
                <sourceElement type="Customer" qualifier="customer" cardinality="one">
                    <modifiers read="true" write="true" search="true" optional="false"/>
                </sourceElement>
                <targetElement type="MyProjectFeatureData" qualifier="featureData" cardinality="many">
                    <modifiers read="true" write="true" search="true" optional="true"/>
                </targetElement>
            </relation>
        </relations>

    </items>
    ```

    --- FILE: myextension/resources/myextension-spring.xml ---
    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <beans xmlns="[http://www.springframework.org/schema/beans](http://www.springframework.org/schema/beans)"
           xmlns:xsi="[http://www.w3.org/2001/XMLSchema-instance](http://www.w3.org/2001/XMLSchema-instance)"
           xmlns:aop="[http://www.springframework.org/schema/aop](http://www.springframework.org/schema/aop)"
           xmlns:context="[http://www.springframework.org/schema/context](http://www.springframework.org/schema/context)"
           xsi:schemaLocation="[http://www.springframework.org/schema/beans](http://www.springframework.org/schema/beans)
           [http://www.springframework.org/schema/beans/spring-beans.xsd](http://www.springframework.org/schema/beans/spring-beans.xsd)
           [http://www.springframework.org/schema/aop](http://www.springframework.org/schema/aop)
           [http://www.springframework.org/schema/aop/spring-aop.xsd](http://www.springframework.org/schema/aop/spring-aop.xsd)
           [http://www.springframework.org/schema/context](http://www.springframework.org/schema/context)
           [http://www.springframework.org/schema/context/spring-context.xsd](http://www.springframework.org/schema/context/spring-context.xsd)">

        <context:annotation-config/> <bean id="myFeatureService" parent="abstractService"
              class="de.myproject.myextension.core.service.impl.DefaultMyFeatureService">
            <property name="myFeatureDAO" ref="myFeatureDAO"/>
            </bean>

        <bean id="myFeatureDAO" parent="abstract            Dao"
              class="de.myproject.myextension.core.dao.impl.DefaultMyFeatureDAO">
            </bean>

        <bean id="myFeatureFacade" class="de.myproject.myextension.facades.impl.DefaultMyFeatureFacade">
            <property name="myFeatureService" ref="myFeatureService"/>
            </bean>

        </beans>
    ```

    --- FILE: myextension/src/myextension/core/service/MyFeatureService.java ---
    ```java
    package de.myproject.myextension.core.service;

    import de.hybris.platform.core.model.customer.CustomerModel;
    import de.myproject.myextension.core.model.MyProjectFeatureDataModel; // Or whatever your custom model is
    import de.myproject.myextension.core.exceptions.MyFeatureServiceException; // Define custom exceptions if necessary

    import java.util.List;
    import java.util.Optional;

    /**
     * Service interface for managing MyProjectFeatureData.
     */
    public interface MyFeatureService {

        /**
         * Creates a new MyProjectFeatureData entry.
         * @param customer The customer associated with the feature.
         * @param someInputParameter A parameter from the HCL code's business logic.
         * @return The newly created MyProjectFeatureDataModel.
         * @throws MyFeatureServiceException if creation fails due to business rules.
         */
        MyProjectFeatureDataModel createMyFeatureData(CustomerModel customer, String someInputParameter) throws MyFeatureServiceException;

        /**
         * Finds MyProjectFeatureData by its unique ID.
         * @param featureId The unique ID.
         * @return An Optional containing the MyProjectFeatureDataModel, or empty if not found.
         */
        Optional<MyProjectFeatureDataModel> getMyFeatureDataById(String featureId);

        /**
         * Retrieves all feature data for a given customer.
         * @param customer The customer.
         * @return A list of MyProjectFeatureDataModels.
         */
        List<MyProjectFeatureDataModel> getFeatureDataForCustomer(CustomerModel customer);

        // Map other HCL Commerce command/logic methods here
    }
    ```

    --- FILE: myextension/src/myextension/core/service/impl/DefaultMyFeatureService.java ---
    ```java
    package de.myproject.myextension.core.service.impl;

    import de.myproject.myextension.core.service.MyFeatureService;
    import de.myproject.myextension.core.dao.MyFeatureDAO;
    import de.myproject.myextension.core.model.MyProjectFeatureDataModel;
    import de.myproject.myextension.core.exceptions.MyFeatureServiceException;
    import de.hybris.platform.core.model.customer.CustomerModel;
    import de.hybris.platform.servicelayer.model.ModelService;
    import de.hybris.platform.servicelayer.search.FlexibleSearchService; // If directly used, but prefer DAO
    import de.hybris.platform.servicelayer.exceptions.ModelSavingException;
    import org.slf4j.Logger;
    import org.slf4j.LoggerFactory;

    import java.util.List;
    import java.util.Optional;

    /**
     * Default implementation of {@link MyFeatureService}.
     */
    public class DefaultMyFeatureService implements MyFeatureService {

        private static final Logger LOG = LoggerFactory.getLogger(DefaultMyFeatureService.class);

        private ModelService modelService;
        private MyFeatureDAO myFeatureDAO;
        // Inject other services like userService, commonI18NService etc. as needed

        @Override
        public MyProjectFeatureDataModel createMyFeatureData(final CustomerModel customer, final String someInputParameter) throws MyFeatureServiceException {
            // Map HCL Commerce business logic here
            // Example:
            if (customer == null) {
                throw new MyFeatureServiceException("Customer cannot be null for feature data creation.");
            }

            final MyProjectFeatureDataModel newFeatureData = modelService.create(MyProjectFeatureDataModel.class);
            newFeatureData.setCustomer(customer);
            newFeatureData.setFeatureId(generateUniqueFeatureId()); // Implement logic based on HCL
            newFeatureData.setStatus(MyProjectFeatureStatus.PENDING);
            newFeatureData.setSomeInputParameter(someInputParameter); // Assuming this attribute exists

            try {
                modelService.save(newFeatureData);
                LOG.info("Created new feature data with ID: {}", newFeatureData.getFeatureId());
                return newFeatureData;
            } catch (final ModelSavingException e) {
                LOG.error("Could not save new feature data for customer {}: {}", customer.getUid(), e.getMessage(), e);
                throw new MyFeatureServiceException("Failed to save feature data.", e);
            }
        }

        @Override
        public Optional<MyProjectFeatureDataModel> getMyFeatureDataById(final String featureId) {
            // Delegate to DAO
            return myFeatureDAO.findMyFeatureDataById(featureId);
        }

        @Override
        public List<MyProjectFeatureDataModel> getFeatureDataForCustomer(final CustomerModel customer) {
            // Delegate to DAO
            return myFeatureDAO.findFeatureDataForCustomer(customer);
        }


        // Helper method (if needed, extracted from HCL logic)
        private String generateUniqueFeatureId() {
            // Implement logic to generate a unique ID, similar to HCL's approach
            // e.g., UUID.randomUUID().toString();
            return "FEATURE_" + System.currentTimeMillis();
        }

        // --- Getters and Setters for injected dependencies ---
        public void setModelService(final ModelService modelService) {
            this.modelService = modelService;
        }

        public void setMyFeatureDAO(final MyFeatureDAO myFeatureDAO) {
            this.myFeatureDAO = myFeatureDAO;
        }
    }
    ```

    --- FILE: myextension/src/myextension/core/dao/MyFeatureDAO.java ---
    ```java
    package de.myproject.myextension.core.dao;

    import de.hybris.platform.core.model.customer.CustomerModel;
    import de.myproject.myextension.core.model.MyProjectFeatureDataModel;

    import java.util.List;
    import java.util.Optional;

    /**
     * Data Access Object for {@link MyProjectFeatureDataModel}.
     */
    public interface MyFeatureDAO {

        /**
         * Finds a single {@link MyProjectFeatureDataModel} by its unique identifier.
         * @param featureId The unique ID of the feature data.
         * @return An {@link Optional} containing the found model, or empty if not found.
         */
        Optional<MyProjectFeatureDataModel> findMyFeatureDataById(String featureId);

        /**
         * Finds all {@link MyProjectFeatureDataModel}s associated with a specific customer.
         * @param customer The customer model.
         * @return A list of {@link MyProjectFeatureDataModel}s, or an empty list if none are found.
         */
        List<MyProjectFeatureDataModel> findFeatureDataForCustomer(CustomerModel customer);

        // Map other HCL data retrieval methods here
    }
    ```

    --- FILE: myextension/src/myextension/core/dao/impl/DefaultMyFeatureDAO.java ---
    ```java
    package de.myproject.myextension.core.dao.impl;

    import de.myproject.myextension.core.dao.MyFeatureDAO;
    import de.myproject.myextension.core.model.MyProjectFeatureDataModel;
    import de.hybris.platform.core.model.customer.CustomerModel;
    import de.hybris.platform.servicelayer.search.FlexibleSearchQuery;
    import de.hybris.platform.servicelayer.search.FlexibleSearchService;
    import de.hybris.platform.servicelayer.search.SearchResult;
    import de.hybris.platform.servicelayer.internal.dao.DefaultGenericDao; // Can be extended, or use FlexibleSearchService directly
    import org.slf4j.Logger;
    import org.slf4j.LoggerFactory;

    import java.util.Collections;
    import java.util.HashMap;
    import java.util.List;
    import java.util.Map;
    import java.util.Optional;

    /**
     * Default implementation of {@link MyFeatureDAO}.
     */
    public class DefaultMyFeatureDAO implements MyFeatureDAO {

        private static final Logger LOG = LoggerFactory.getLogger(DefaultMyFeatureDAO.class);

        private FlexibleSearchService flexibleSearchService;

        @Override
        public Optional<MyProjectFeatureDataModel> findMyFeatureDataById(final String featureId) {
            final String query = "SELECT {pk} FROM {MyProjectFeatureData} WHERE {featureId} = ?featureId";
            final Map<String, Object> params = new HashMap<>();
            params.put("featureId", featureId);

            final FlexibleSearchQuery fsQuery = new FlexibleSearchQuery(query, params);
            try {
                final SearchResult<MyProjectFeatureDataModel> result = flexibleSearchService.search(fsQuery);
                return result.getResult().stream().findFirst();
            } catch (final Exception e) {
                LOG.error("Error finding MyProjectFeatureData by ID {}: {}", featureId, e.getMessage(), e);
                return Optional.empty(); // Return empty on error, not re-throw
            }
        }

        @Override
        public List<MyProjectFeatureDataModel> findFeatureDataForCustomer(final CustomerModel customer) {
            final String query = "SELECT {pk} FROM {MyProjectFeatureData} WHERE {customer} = ?customerPk";
            final Map<String, Object> params = new HashMap<>();
            params.put("customerPk", customer.getPk());

            final FlexibleSearchQuery fsQuery = new FlexibleSearchQuery(query, params);
            try {
                final SearchResult<MyProjectFeatureDataModel> result = flexibleSearchService.search(fsQuery);
                return result.getResult();
            } catch (final Exception e) {
                LOG.error("Error finding MyProjectFeatureData for customer {}: {}", customer.getUid(), e.getMessage(), e);
                return Collections.emptyList(); // Return empty list on error
            }
        }

        // --- Getters and Setters for injected dependencies ---
        public void setFlexibleSearchService(final FlexibleSearchService flexibleSearchService) {
            this.flexibleSearchService = flexibleSearchService;
        }
    }
    ```

    --- FILE: myextension/web/src/myextension/controllers/pages/MyFeatureController.java ---
    ```java
    package de.myproject.myextension.controllers.pages; // For storefront/accelerator based controllers

    import de.myproject.myextension.facades.MyFeatureFacade; // Use Facade if exposing to frontend
    import de.myproject.myextension.data.MyFeatureDataDTO; // Example DTO if needed for response
    import de.myproject.myextension.core.exceptions.MyFeatureServiceException;
    import de.hybris.platform.acceleratorstorefrontcommons.controllers.pages.Abstract () PageController; // For storefront
    import de.hybris.platform.acceleratorstorefrontcommons.annotations.RequireHardLogIn; // Example security annotation
    import de.hybris.platform.acceleratorstorefrontcommons.breadcrumb.Breadcrumb;
    import de.hybris.platform.acceleratorstorefrontcommons.constants.WebConstants; // For error messages etc.
    import org.springframework.stereotype.Controller;
    import org.springframework.ui.Model;
    import org.springframework.web.bind.annotation.RequestMapping;
    import org.springframework.web.bind.annotation.RequestMethod;
    import org.springframework.web.bind.annotation.RequestParam;
    import org.springframework.web.servlet.mvc.support.RedirectAttributes;
    import org.slf4j.Logger;
    import org.slf4j.LoggerFactory;

    import javax.annotation.Resource; // For @Resource annotation

    import static de.hybris.platform.acceleratorstorefrontcommons.controllers.AbstractPageController.REDIRECT_PREFIX; // For redirects


    /**
     * Controller for MyFeature functionality.
     */
    @Controller
    @RequestMapping("/myfeature")
    public class MyFeatureController extends AbstractPageController {

        private static final Logger LOG = LoggerFactory.getLogger(MyFeatureController.class);

        @Resource(name = "myFeatureFacade") // Inject Facade
        private MyFeatureFacade myFeatureFacade;

        // Example: Display a feature page
        @RequestMapping(value = "/view", method = RequestMethod.GET)
        @RequireHardLogIn // Example: requires logged in user
        public String viewMyFeaturePage(final Model model) {
            // Add page title, meta data, etc.
            storeCmsPageInModel(model, getContentPageForLabelOrId("myFeaturePage"));
            setUpMetaDataForContentPage(model, getContentPageForLabelOrId("myFeaturePage"));
            model.addAttribute(WebConstants.BREADCRUMBS_KEY,
                simple"/>Breadcrumb.builder().target("/myfeature/view").title("My Feature").build()));

            try {
                // Fetch data using facade
                final MyFeatureDataDTO featureData = myFeatureFacade.getMyFeatureForCurrentUser();
                model.addAttribute("featureData", featureData);
            } catch (final Exception e) {
                LOG.error("Error fetching my feature data: {}", e.getMessage(), e);
                // Add global error message
                GlobalMessages.addErrorMessage(model, "myfeature.error.loading");
            }
            return getViewForPage(model);
        }

        // Example: Process a form submission for the feature (e.g., enable/disable)
        @RequestMapping(value = "/process", method = RequestMethod.POST)
        @RequireHardLogIn
        public String processMyFeature(@RequestParam("action") final String action,
                                        final RedirectAttributes redirectAttributes) {
            try {
                // Delegate to facade
                myFeatureFacade.processFeatureAction(action);
                GlobalMessages.addFlashMessage(redirectAttributes, GlobalMessages.CONF_MESSAGES_HOLDER, "myfeature.success.processed");
                return REDIRECT_PREFIX + "/myfeature/view";
            } catch (final MyFeatureServiceException e) { // Catch specific business exceptions
                LOG.error("Failed to process feature action '{}': {}", action, e.getMessage(), e);
                GlobalMessages.addFlashMessage(redirectAttributes, GlobalMessages.ERROR_MESSAGES_HOLDER, "myfeature.error.processing");
                return REDIRECT_PREFIX + "/myfeature/view";
            } catch (final Exception e) {
                LOG.error("An unexpected error occurred while processing feature action '{}': {}", action, e.getMessage(), e);
                GlobalMessages.addFlashMessage(redirectAttributes, GlobalMessages.ERROR_MESSAGES_HOLDER, "myfeature.error.general");
                return REDIRECT_PREFIX + "/myfeature/view";
            }
        }
    }
    ```

    --- FILE: myextension/acceleratoraddon/web/webroot/WEB-INF/views/responsive/pages/myfeature/myFeaturePage.jsp ---
    ```jsp
    <%--
        MyFeaturePage.jsp - Sample JSP for the MyFeatureController.
        This file would contain the presentation logic using JSTL/Spring tags,
        and display data retrieved by the controller from the facade.
    --%>
    <%@ page language="java" contentType="text/html; charset=UTF-8"
        pageEncoding="UTF-8"%>
    <%@ taglib prefix="c" uri="[http://java.sun.com/jsp/jstl/core](http://java.sun.com/jsp/jstl/core)"%>
    <%@ taglib prefix="spring" uri="[http://www.springframework.org/tags](http://www.springframework.org/tags)"%>
    <%@ taglib prefix="form" uri="[http://www.springframework.org/tags/form](http://www.springframework.org/tags/form)"%>
    <%@ taglib prefix="cms" uri="[http://hybris.com/cms2/tags](http://hybris.com/cms2/tags)"%>
    <%@ taglib prefix="fn" uri="[http://java.sun.com/jsp/jstl/functions](http://java.sun.com/jsp/jstl/functions)" %>

    <spring:url value="/myfeature/process" var="processFeatureUrl"/>

    <cms:pageSlot position="MyFeatureContent" var="featureContent">
        <cms:component component="${featureContent}"/>
    </cms:pageSlot>

    <div class="my-feature-container">
        <h1><spring:theme code="myfeature.page.title"/></h1>

        <c:if test="${not empty featureData}">
            <p>Feature ID: ${featureData.featureId}</p>
            <p>Status: ${featureData.status}</p>
            <p>Last Processed: ${featureData.lastProcessedDate}</p>
            </c:if>
        <c:if test="${empty featureData}">
            <p><spring:theme code="myfeature.no.data.found"/></p>
        </c:if>

        <form action="${processFeatureUrl}" method="post">
            <button type="submit" name="action" value="enable">Enable Feature</button>
            <button type="submit" name="action" value="disable">Disable Feature</button>
            <input type="hidden" name="${_csrf.parameterName}" value="${_csrf.token}"/>
        </form>

        <div class="messages">
            <cms:pageSlot position="GlobalMessages" var="globalMessages">
                <cms:component component="${globalMessages}"/>
            </cms:pageSlot>
        </div>
    </div>
    ```

    --- FILE: myextension/resources/myextension_en.properties ---
    ```properties
    # Labels for myextension
    myfeature.page.title=My Custom Feature
    myfeature.error.loading=Failed to load feature data. Please try again.
    myfeature.success.processed=Feature action processed successfully.
    myfeature.error.processing=Error processing feature action.
    myfeature.error.general=An unexpected error occurred.
    myfeature.no.data.found=No feature data available.
    ```
    """
    return prompt.strip()


def generate_conversion_prompt_openai(hcl_code_content, flow_description, sap_examples=None, filename=""):
    """
    Constructs the prompt for OpenAI models using a loaded template.
    """
    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z%z")

    # The prompt now uses f-string like placeholders for dynamic content
    # The template itself should contain placeholders like {hcl_code_content}, {flow_description}, etc.
    # Note: sap_examples section needs conditional formatting, so it's a bit trickier with pure f-strings in a file.
    # We'll use .format() and handle the optional part separately.

    base_prompt = GLOBAL_PROMPT_TEMPLATE

    # Handle the optional sap_examples section
    if sap_examples:
        # If the template has a dedicated {sap_examples} placeholder, populate it directly
        # Otherwise, you might need to insert it more dynamically
        # For our current prompt, it's already structured to accept it directly
        sap_examples_section = f"""
        **SAP Commerce Framework Examples/Best Practices (for reference):**
        (These examples demonstrate how SAP Commerce components are typically structured. Please adhere to these patterns.
        They might include sample `items.xml`, service/DAO/controller implementations, or Spring configurations.)
        ```sap_commerce_examples
        {sap_examples}
        ```
        """
    else:
        # Remove the placeholder or the entire block if no examples are provided
        # This requires the template to have a clear way to identify the examples block.
        # A simple way for this prompt structure is to replace it with an empty string
        # if the template has the {sap_examples} placeholder.
        sap_examples_section = ""
        # If your template explicitly includes the examples section even when empty,
        # you might need to carefully remove it using regex or string manipulation
        # if you don't want the heading to appear without content.
        # For simplicity, if {sap_examples} is just a placeholder, passing an empty string
        # will work if the template is well-designed.


    # Use .format() to fill in the variables
    # Ensure all placeholders in your .txt file are covered here.
    formatted_prompt = base_prompt.format(
        current_datetime=current_datetime,
        hcl_code_content=hcl_code_content,
        flow_description=flow_description,
        filename=filename,
        sap_examples=sap_examples_section.strip() # Pass the formatted section or empty string
    )

    return formatted_prompt.strip()

def process_hcl_feature(hcl_code_filepaths, flow_filepath, sap_examples_dir):
    """
    Processes an HCL Commerce feature for conversion.
    """
    all_hcl_code = ""
    for fp in hcl_code_filepaths:
        content = read_file_content(fp)
        if content:
            all_hcl_code += f"\n--- Start of file: {os.path.basename(fp)} ---\n"
            all_hcl_code += content
            all_hcl_code += f"\n--- End of file: {os.path.basename(fp)} ---\n"

    flow_description = read_file_content(flow_filepath)
    if not all_hcl_code or not flow_description:
        print(f"Skipping feature due to missing code or flow description: {flow_filepath}")
        return

    sap_examples_content = None
    if sap_examples_dir and os.path.exists(sap_examples_dir):
        sap_examples_content = ""
        for root, _, files in os.walk(sap_examples_dir):
            for file in files:
                filepath = os.path.join(root, file)
                content = read_file_content(filepath)
                if content:
                    sap_examples_content += f"\n--- Start of SAP Example: {os.path.basename(filepath)} ---\n"
                    sap_examples_content += content
                    sap_examples_content += f"\n--- End of SAP Example: {os.path.basename(filepath)} ---\n"

    # Use the name of the flow file (without extension) as a feature identifier for logs
    feature_name = os.path.splitext(os.path.basename(flow_filepath))[0]
    log_filepath = os.path.join(OUTPUT_CONVERSION_LOGS_DIR, f"{feature_name}_conversion_log.txt")

    print(f"Generating prompt for feature: {feature_name}")
    #prompt = generate_conversion_prompt(all_hcl_code, flow_description, sap_examples_content, filename=os.path.basename(hcl_code_filepaths[0] if hcl_code_filepaths else "N/A")) # Using first HCL file name for context
    prompt = generate_conversion_prompt_openai(all_hcl_code, flow_description, sap_examples_content, filename=os.path.basename(hcl_code_filepaths[0] if hcl_code_filepaths else "N/A"))

    try:
        # Send to Gemini Code Assist
        print("Sending request to Gemini Code Assist...")
        response = model.generate_content(prompt)
        converted_code_text = response.text
        print("Received response from Gemini Code Assist.")

        # Log the full response for review
        write_file_content(log_filepath, f"Prompt:\n{prompt}\n\n--- Gemini Response ---\n{converted_code_text}")

        # Parse the output and write to files
        # This parsing needs to be robust as LLM output format can vary.
        # A simple delimiter based parsing is shown here.
        output_files = converted_code_text.split('--- FILE: ')[1:] # Split by delimiter
        for file_section in output_files:
            try:
                # Extract path and content
                lines = file_section.split('\n', 1)
                if len(lines) < 2:
                    print(f"Skipping malformed output section: {file_section[:50]}...")
                    continue

                relative_path = lines[0].strip()
                code_content = lines[1].strip()

                if relative_path.startswith('---'):
                    relative_path = relative_path.lstrip('-').strip()
                if relative_path.endswith('---'):
                    relative_path = relative_path.rstrip('-').strip()
                

                # Remove markdown code block fences if present
                if code_content.startswith("```") and code_content.endswith("```"):
                    code_content = code_content.lstrip("`").lstrip(code_content.split('\n')[0]).rstrip("`").strip()

                # Construct full output path
                output_filepath = os.path.join(OUTPUT_SAP_CODE_DIR, relative_path)
                os.makedirs(os.path.dirname(output_filepath), exist_ok=True) # Ensure subdirectories exist
                write_file_content(output_filepath, code_content)
            except Exception as e:
                print(f"Error parsing and writing individual file section: {e}\nSection:\n{file_section[:200]}...")

    except Exception as e:
        print(f"Error communicating with Gemini Code Assist or processing response for feature {feature_name}: {e}")
        write_file_content(log_filepath, f"Error: {e}\nPrompt:\n{prompt}")


def main():
    # Map HCL code files to their respective flow descriptions
    # This is a manual mapping step based on your understanding of the features.
    # Example:
    features_to_process = {
       # "invoice_display_feature": {
       #     "hcl_code": [
       #         os.path.join(INPUT_HCL_CODE_DIR, 'views-ext.xml'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'LINPayInvoiceResults.jsp'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'GetInvoicesTaskCmd.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'GetInvoicesTaskCmdImpl.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'GetInvoicesDTO.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'DisplayInvoicesDataBean.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'DisplayInvoicesDataBeanHandler.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'isplayInvoicesDataBean.xml')
                # Add all relevant HCL code files for this feature
       #     ],
       #     "flow_description": os.path.join(INPUT_FLOW_DESCRIPTIONS_DIR, 'RequestFlow.txt'),
            #"sap_examples": os.path.join(INPUT_SAP_EXAMPLES_DIR, 'examples') # Optional
            
        #},
        "account_balance_feature": {
            "hcl_code": [
                os.path.join(INPUT_HCL_CODE_DIR, 'views-ext.xml'),
                os.path.join(INPUT_HCL_CODE_DIR, 'LINGetAccountBalance.jsp'),
                os.path.join(INPUT_HCL_CODE_DIR, 'LINMyAccountSelfServicesHandler.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'AccountBalanceAndStatementsTaskCmdImpl.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'AccountBalanceAndStatementsTaskCmd.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'AccountBalanceAndStatementsCmdImpl.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'AccountBalanceAndStatementsCmd.java')
                # Add all relevant HCL code files for this feature
            ],
            "flow_description": os.path.join(INPUT_FLOW_DESCRIPTIONS_DIR, 'RequestFlow.txt'),
            #"sap_examples": os.path.join(INPUT_SAP_EXAMPLES_DIR, 'examples') # Optional
            
        },
        # Add more features as needed
    }

    for feature_name, details in features_to_process.items():
        print(f"\n--- Processing Feature: {feature_name} ---")
        process_hcl_feature(details["hcl_code"], details["flow_description"], details.get("sap_examples"))

    print("\nCode conversion process completed. Please review the output_folder for generated code and logs.")
    print("Manual review, testing, and potential refactoring of the generated SAP Commerce code are essential.")

if __name__ == "__main__":
    main()