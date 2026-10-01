"use client";

import Link from "next/link";
import {
  useEffect,
  useMemo,
  useState
} from "react";

import {
  API_BASE_URL,
  apiGet
} from "@/lib/api";


type Product = {
  id: string;
  name: string;
  brand: string | null;
  sku: string | null;
  gtin: string | null;
  description: string | null;
  attributes: Record<string, unknown>;
  metadata: Record<string, unknown>;
  isActive: boolean;
  classificationCount: number;
  classificationRequestCount: number;
  manufacturerProductCount: number;
};


type Classification = {
  id: string;
  hsCode: string;
  hsDescription: string;
  level: number;
  countryIso2: string | null;
  countryName: string | null;
  isPrimary: boolean;
  confidence: number | null;
  decisionMethod: string | null;
};


type Specification = {
  id: string;
  definitionCode: string;
  definitionName: string;
  category: string | null;
  valueType: string;
  qualifier: string;
  numericValue: number | null;
  minimumValue: number | null;
  maximumValue: number | null;
  textValue: string | null;
  booleanValue: boolean | null;
  uomCode: string | null;
  uomSymbol: string | null;
  sourceType: string;
  confidence: number | null;
};


type ManufacturerProduct = {
  id: string;
  productId: string;
  manufacturerId: string;
  manufacturerLegalName: string;
  manufacturerTradingName: string | null;
  originCountryIso2: string | null;
  originCountryName: string | null;
  name: string;
  brand: string | null;
  grade: string | null;
  modelCode: string | null;
  sku: string | null;
  gtin: string | null;
  description: string | null;
  status: string;
};


type Packaging = {
  id: string;
  manufacturerProductId: string;
  packageTypeCode: string;
  packageTypeName: string;
  name: string;
  packagingLevel: string;
  packagingMaterial: string | null;
  contentQuantity: number | null;
  contentUomCode: string | null;
  innerPackagingName: string | null;
  innerPackageCount: number | null;
  netWeight: number | null;
  grossWeight: number | null;
  weightUomCode: string | null;
  length: number | null;
  width: number | null;
  height: number | null;
  dimensionUomCode: string | null;
  isDefault: boolean;
  sourceType: string;
};


type CommercialOffer = {
  id: string;
  sellerId: string;
  sellerLegalName: string;
  buyerId: string | null;
  buyerLegalName: string | null;
  manufacturerProductId: string;
  manufacturerProductName: string;
  packagingConfigurationId: string | null;
  packagingName: string | null;
  offerReference: string | null;
  status: string;
  unitPrice: number;
  currencyCode: string;
  currencyName: string;
  priceUomCode: string;
  priceUomSymbol: string | null;
  minimumOrderQuantity: number | null;
  minimumOrderUomCode: string | null;
  leadTimeDays: number | null;
  paymentTerms: string | null;
  incotermEdition: number;
  incotermCode: string;
  incotermName: string;
  incotermTransportScope: string;
  namedLocationRole: string;
  namedPlaceText: string | null;
  namedTradeLocationUnlocode: string | null;
  namedTradeLocationName: string | null;
  namedOrganizationSiteName: string | null;
  validFrom: string | null;
  validTo: string | null;
  sourceType: string;
  evidenceCount: number;
};


type LandedCostComponent = {
  id: string;
  componentTypeCode: string;
  componentTypeName: string;
  componentCategory: string;
  sequence: number;
  description: string | null;
  includedInOffer: boolean;
  calculationMethod: string;
  sourceAmount: number | null;
  sourceCurrencyCode: string | null;
  exchangeRateToScenario: number | null;
  percentageRate: number | null;
  taxableBaseScenarioCurrency: number | null;
  amountScenarioCurrency: number;
  sourceType: string;
  evidenceCount: number;
};


type LandedCostScenario = {
  id: string;
  commercialOfferId: string;
  commercialOfferReference: string | null;
  sellerId: string;
  sellerLegalName: string;
  manufacturerProductId: string;
  manufacturerProductName: string;
  productId: string;
  productName: string;
  incotermEdition: number;
  incotermCode: string;
  offerNamedPlaceText: string | null;
  offerNamedTradeLocationUnlocode: string | null;
  scenarioReference: string | null;
  status: string;
  targetQuantity: number;
  targetUomCode: string;
  targetUomSymbol: string | null;
  scenarioCurrencyCode: string;
  destinationCountryIso2: string;
  destinationCountryName: string;
  destinationTradeLocationUnlocode: string | null;
  destinationTradeLocationName: string | null;
  destinationOrganizationSiteName: string | null;
  destinationPlaceText: string | null;
  offerFxRateToScenario: number;
  offerFxRateDate: string | null;
  offerFxSource: string | null;
  offerAmountSourceCurrency: number;
  offerCurrencyCode: string;
  offerAmountScenarioCurrency: number;
  includedComponentTotalScenarioCurrency: number;
  addedComponentTotalScenarioCurrency: number;
  landedCostTotalScenarioCurrency: number;
  landedCostPerTargetUom: number;
  sourceType: string;
  evidenceCount: number;
  components: LandedCostComponent[];
};


type SiteLink = {
  id: string;
  relationshipType: string;
  siteId: string;
  siteName: string;
  siteType: string;
  siteOrganizationLegalName: string;
  siteCountryIso2: string | null;
  siteCountryName: string | null;
  sourceType: string;
  confidence: number | null;
};


type ProductDocument = {
  id: string;
  productId: string | null;
  manufacturerProductId: string | null;
  typeCode: string;
  typeName: string;
  category: string;
  issuerLegalName: string | null;
  title: string;
  documentNumber: string | null;
  issueDate: string | null;
  expiryDate: string | null;
  status: string;
  verificationStatus: string;
  fileName: string | null;
  storageUri: string | null;
  sourceType: string;
  evidenceCount: number;
};


type ComplianceRecord = {
  id: string;
  frameworkCode: string;
  frameworkName: string;
  authority: string | null;
  jurisdictionCountryIso2: string | null;
  requirementCode: string | null;
  registrationNumber: string | null;
  complianceStatus: string;
  evidenceDocumentId: string | null;
  validFrom: string | null;
  validTo: string | null;
  sourceType: string;
  evidenceCount: number;
};


type Counterparty = {
  id: string;
  legalName: string;
  tradingName: string | null;
  website: string | null;
  country: {
    iso2: string;
    name: string;
  } | null;
  roles: string[];
  matchedActivityCount: number;
  matchedActivities: Array<{
    id: string;
    activityType: string;
    confidence: number | null;
    marketCountry: {
      iso2: string;
      name: string;
    } | null;
    hsCode: {
      code: string;
      description: string;
    } | null;
    evidenceCount: number;
  }>;
};


type Collection<T> = {
  ok: boolean;
  [key: string]: unknown;
};


const tabs = [
  "Overview",
  "Classification",
  "Specifications",
  "Manufacturer Products",
  "Packaging",
  "Offers",
  "Landed Cost",
  "Sites",
  "Documents",
  "Compliance",
  "Counterparties"
] as const;


type Tab =
  typeof tabs[number];


function displayValue(
  specification: Specification
) {

  if (
    specification.valueType
    === "numeric"
  ) {

    const unit =
      specification.uomSymbol
      ?? specification.uomCode
      ?? "";


    if (
      specification.qualifier
      === "range"
    ) {

      return (
        `${specification.minimumValue ?? "?"}–${specification.maximumValue ?? "?"} ${unit}`
      ).trim();

    }


    const value =
      specification.numericValue
      ?? specification.minimumValue
      ?? specification.maximumValue;


    const prefix =
      specification.qualifier
      === "minimum"
        ? "≥ "
        : specification.qualifier
          === "maximum"
            ? "≤ "
            : "";


    return (
      `${prefix}${value ?? "—"} ${unit}`
    ).trim();

  }


  if (
    specification.valueType
    === "boolean"
  ) {

    return specification.booleanValue
      ? "Yes"
      : "No";

  }


  return (
    specification.textValue
    ?? "—"
  );

}


function DataRow({
  label,
  value
}: {
  label: string;
  value:
    string
    | number
    | null
    | undefined;
}) {

  return (
    <div className="data-row">
      <span>
        {label}
      </span>
      <strong>
        {
          value === null
          || value === undefined
          || value === ""
            ? "—"
            : value
        }
      </strong>
    </div>
  );

}


function SectionTitle({
  kicker,
  title,
  description
}: {
  kicker: string;
  title: string;
  description?: string;
}) {

  return (
    <div className="section-title">
      <p className="section-kicker">
        {kicker}
      </p>
      <h2>
        {title}
      </h2>
      {
        description
          ? (
              <p>
                {description}
              </p>
            )
          : null
      }
    </div>
  );

}


export function ProductWorkbench({
  productId
}: {
  productId: string;
}) {

  const [
    activeTab,
    setActiveTab
  ] =
    useState<Tab>(
      "Overview"
    );

  const [
    product,
    setProduct
  ] =
    useState<Product | null>(
      null
    );

  const [
    classifications,
    setClassifications
  ] =
    useState<Classification[]>([]);

  const [
    specifications,
    setSpecifications
  ] =
    useState<Specification[]>([]);

  const [
    manufacturerProducts,
    setManufacturerProducts
  ] =
    useState<ManufacturerProduct[]>([]);

  const [
    packagingByProduct,
    setPackagingByProduct
  ] =
    useState<Record<string, Packaging[]>>({});

  const [
    offersByProduct,
    setOffersByProduct
  ] =
    useState<Record<string, CommercialOffer[]>>({});

  const [
    landedCostScenarios,
    setLandedCostScenarios
  ] =
    useState<LandedCostScenario[]>([]);

  const [
    sitesByProduct,
    setSitesByProduct
  ] =
    useState<Record<string, SiteLink[]>>({});

  const [
    documents,
    setDocuments
  ] =
    useState<ProductDocument[]>([]);

  const [
    compliance,
    setCompliance
  ] =
    useState<ComplianceRecord[]>([]);

  const [
    manufacturerDocuments,
    setManufacturerDocuments
  ] =
    useState<Record<string, ProductDocument[]>>({});

  const [
    manufacturerCompliance,
    setManufacturerCompliance
  ] =
    useState<Record<string, ComplianceRecord[]>>({});

  const [
    counterparties,
    setCounterparties
  ] =
    useState<Counterparty[]>([]);

  const [
    loading,
    setLoading
  ] =
    useState(true);

  const [
    detailLoading,
    setDetailLoading
  ] =
    useState(false);

  const [
    error,
    setError
  ] =
    useState<string | null>(
      null
    );


  useEffect(
    () => {

      let cancelled =
        false;


      async function loadCore() {

        setLoading(
          true
        );

        setError(
          null
        );


        try {

          const [
            productResponse,
            classificationResponse,
            specificationResponse,
            manufacturerResponse,
            documentResponse,
            complianceResponse,
            counterpartyResponse,
            landedCostResponse
          ] =
            await Promise.all([

              apiGet<{
                product: Product;
              }>(
                `/api/products/${productId}`
              ),

              apiGet<{
                classifications: Classification[];
              }>(
                `/api/products/${productId}/classifications`
              ),

              apiGet<{
                specifications: Specification[];
              }>(
                `/api/products/${productId}/specifications`
              ),

              apiGet<{
                manufacturerProducts: ManufacturerProduct[];
              }>(
                `/api/products/${productId}/manufacturer-products?limit=100`
              ),

              apiGet<{
                documents: ProductDocument[];
              }>(
                `/api/products/${productId}/documents`
              ),

              apiGet<{
                compliance: ComplianceRecord[];
              }>(
                `/api/products/${productId}/compliance`
              ),

              apiGet<{
                organizations: Counterparty[];
              }>(
                `/api/intelligence/counterparties?productId=${productId}&limit=100`
              ),

              apiGet<{
                scenarios: LandedCostScenario[];
              }>(
                `/api/landed-cost/scenarios?productId=${productId}&limit=100`
              )

            ]);


          if (cancelled) {

            return;

          }


          setProduct(
            productResponse.product
          );

          setClassifications(
            classificationResponse.classifications
          );

          setSpecifications(
            specificationResponse.specifications
          );

          setManufacturerProducts(
            manufacturerResponse.manufacturerProducts
          );

          setDocuments(
            documentResponse.documents
          );

          setCompliance(
            complianceResponse.compliance
          );

          setCounterparties(
            counterpartyResponse.organizations
          );

          setLandedCostScenarios(
            landedCostResponse.scenarios
          );

        }
        catch {

          if (!cancelled) {

            setError(
              "The Product Workbench could not load its canonical API data."
            );

          }

        }
        finally {

          if (!cancelled) {

            setLoading(
              false
            );

          }

        }

      }


      void loadCore();


      return () => {

        cancelled =
          true;

      };

    },
    [
      productId
    ]
  );


  useEffect(
    () => {

      if (
        manufacturerProducts.length
        === 0
      ) {

        return;

      }


      if (
        ![
          "Packaging",
          "Offers",
          "Sites",
          "Documents",
          "Compliance"
        ].includes(
          activeTab
        )
      ) {

        return;

      }


      let cancelled =
        false;


      async function loadManufacturerDetails() {

        setDetailLoading(
          true
        );


        try {

          const results =
            await Promise.all(
              manufacturerProducts.map(
                async item => {

                  const [
                    packagingResponse,
                    offerResponse,
                    siteResponse,
                    documentResponse,
                    complianceResponse
                  ] =
                    await Promise.all([

                      apiGet<{
                        packaging: Packaging[];
                      }>(
                        `/api/manufacturer-products/${item.id}/packaging`
                      ),

                      apiGet<{
                        offers: CommercialOffer[];
                      }>(
                        `/api/commercial-offers?manufacturerProductId=${item.id}&limit=100`
                      ),

                      apiGet<{
                        sites: SiteLink[];
                      }>(
                        `/api/manufacturer-products/${item.id}/sites`
                      ),

                      apiGet<{
                        documents: ProductDocument[];
                      }>(
                        `/api/manufacturer-products/${item.id}/documents`
                      ),

                      apiGet<{
                        compliance: ComplianceRecord[];
                      }>(
                        `/api/manufacturer-products/${item.id}/compliance`
                      )

                    ]);


                  return {
                    id:
                      item.id,
                    packaging:
                      packagingResponse.packaging,
                    offers:
                      offerResponse.offers,
                    sites:
                      siteResponse.sites,
                    documents:
                      documentResponse.documents,
                    compliance:
                      complianceResponse.compliance
                  };

                }
              )
            );


          if (cancelled) {

            return;

          }


          setPackagingByProduct(
            Object.fromEntries(
              results.map(
                item => [
                  item.id,
                  item.packaging
                ]
              )
            )
          );

          setOffersByProduct(
            Object.fromEntries(
              results.map(
                item => [
                  item.id,
                  item.offers
                ]
              )
            )
          );

          setSitesByProduct(
            Object.fromEntries(
              results.map(
                item => [
                  item.id,
                  item.sites
                ]
              )
            )
          );

          setManufacturerDocuments(
            Object.fromEntries(
              results.map(
                item => [
                  item.id,
                  item.documents
                ]
              )
            )
          );

          setManufacturerCompliance(
            Object.fromEntries(
              results.map(
                item => [
                  item.id,
                  item.compliance
                ]
              )
            )
          );

        }
        catch {

          if (!cancelled) {

            setError(
              "Some manufacturer-level Product data could not be loaded."
            );

          }

        }
        finally {

          if (!cancelled) {

            setDetailLoading(
              false
            );

          }

        }

      }


      void loadManufacturerDetails();


      return () => {

        cancelled =
          true;

      };

    },
    [
      activeTab,
      manufacturerProducts
    ]
  );


  const primaryClassification =
    useMemo(
      () =>
        classifications.find(
          item =>
            item.isPrimary
        )
        ?? classifications[0]
        ?? null,
      [
        classifications
      ]
    );


  if (loading) {

    return (
      <main className="shell">
        <div className="workbench-loading">
          Loading Product Workbench…
        </div>
      </main>
    );

  }


  if (
    error
    && !product
  ) {

    return (
      <main className="shell">
        <div className="empty-state error-state">
          <strong>
            Product Workbench unavailable
          </strong>
          <p>
            {error}
          </p>
          <p>
            API: {API_BASE_URL}
          </p>
          <Link href="/">
            Return to Products
          </Link>
        </div>
      </main>
    );

  }


  if (!product) {

    return null;

  }


  return (
    <main className="shell workbench-shell">

      <div className="breadcrumb">
        <Link href="/">
          Products
        </Link>
        <span>
          /
        </span>
        <strong>
          {product.name}
        </strong>
      </div>


      <header className="workbench-header">

        <div>

          <div className="headline-meta">

            <span className="status-badge">
              {
                product.isActive
                  ? "ACTIVE"
                  : "INACTIVE"
              }
            </span>

            {
              primaryClassification
                ? (
                    <span className="hs-badge">
                      HS {primaryClassification.hsCode}
                    </span>
                  )
                : null
            }

          </div>

          <h1>
            {product.name}
          </h1>

          <p>
            {
              product.description
              ?? "No Product description has been recorded."
            }
          </p>

        </div>

        <div className="workbench-metrics">

          <div>
            <span>
              HS classifications
            </span>
            <strong>
              {classifications.length}
            </strong>
          </div>

          <div>
            <span>
              Manufacturer Products
            </span>
            <strong>
              {manufacturerProducts.length}
            </strong>
          </div>

          <div>
            <span>
              Counterparties
            </span>
            <strong>
              {counterparties.length}
            </strong>
          </div>

        </div>

      </header>


      <nav
        className="tabs"
        aria-label="Product Workbench"
      >

        {
          tabs.map(
            tab => (
              <button
                type="button"
                key={tab}
                className={
                  activeTab === tab
                    ? "tab active"
                    : "tab"
                }
                onClick={
                  () =>
                    setActiveTab(
                      tab
                    )
                }
              >
                {tab}
              </button>
            )
          )
        }

      </nav>


      {error
        ? (
            <div className="inline-warning">
              {error}
            </div>
          )
        : null}


      <section className="panel workbench-panel">

        {
          activeTab === "Overview"
            ? (
                <>

                  <SectionTitle
                    kicker="PRODUCT"
                    title="Canonical identity"
                    description="The generic trade Product remains separate from manufacturer grades, SKUs and packaging."
                  />

                  <div className="two-column-grid">

                    <div className="data-card">

                      <DataRow
                        label="Name"
                        value={product.name}
                      />

                      <DataRow
                        label="Legacy brand"
                        value={product.brand}
                      />

                      <DataRow
                        label="Legacy SKU"
                        value={product.sku}
                      />

                      <DataRow
                        label="GTIN"
                        value={product.gtin}
                      />

                    </div>

                    <div className="data-card">

                      <DataRow
                        label="Accepted classifications"
                        value={product.classificationCount}
                      />

                      <DataRow
                        label="Classification requests"
                        value={product.classificationRequestCount}
                      />

                      <DataRow
                        label="Manufacturer Products"
                        value={product.manufacturerProductCount}
                      />

                      <DataRow
                        label="API"
                        value={API_BASE_URL}
                      />

                    </div>

                  </div>

                </>
              )
            : null
        }


        {
          activeTab === "Classification"
            ? (
                <>

                  <SectionTitle
                    kicker="CLASSIFICATION"
                    title="Accepted HS classifications"
                    description="Only explicitly accepted classifications are shown here."
                  />

                  {
                    classifications.length === 0
                      ? (
                          <div className="empty-state">
                            No accepted HS classification.
                          </div>
                        )
                      : (
                          <div className="stack-list">
                            {
                              classifications.map(
                                item => (
                                  <article
                                    className="record-card"
                                    key={item.id}
                                  >
                                    <div>
                                      <span className="record-code">
                                        HS {item.hsCode}
                                      </span>
                                      <h3>
                                        {item.hsDescription}
                                      </h3>
                                    </div>
                                    <div className="record-meta">
                                      <span>
                                        {
                                          item.countryIso2
                                          ?? "Global"
                                        }
                                      </span>
                                      <span>
                                        {
                                          item.isPrimary
                                            ? "Primary"
                                            : "Accepted"
                                        }
                                      </span>
                                      <span>
                                        {
                                          item.decisionMethod
                                          ?? "Decision recorded"
                                        }
                                      </span>
                                    </div>
                                  </article>
                                )
                              )
                            }
                          </div>
                        )
                  }

                </>
              )
            : null
        }


        {
          activeTab === "Specifications"
            ? (
                <>

                  <SectionTitle
                    kicker="SPECIFICATIONS"
                    title="Structured Product properties"
                    description="Typed values are backed by canonical specification definitions and UOMs."
                  />

                  {
                    specifications.length === 0
                      ? (
                          <div className="empty-state">
                            No generic Product specifications have been recorded.
                          </div>
                        )
                      : (
                          <div className="spec-grid">
                            {
                              specifications.map(
                                item => (
                                  <article
                                    className="spec-card"
                                    key={item.id}
                                  >
                                    <span>
                                      {
                                        item.category
                                        ?? "Specification"
                                      }
                                    </span>
                                    <h3>
                                      {item.definitionName}
                                    </h3>
                                    <strong>
                                      {
                                        displayValue(
                                          item
                                        )
                                      }
                                    </strong>
                                    <small>
                                      {item.qualifier}
                                      {" · "}
                                      {item.sourceType}
                                    </small>
                                  </article>
                                )
                              )
                            }
                          </div>
                        )
                  }

                </>
              )
            : null
        }


        {
          activeTab === "Manufacturer Products"
            ? (
                <>

                  <SectionTitle
                    kicker="MANUFACTURER PRODUCTS"
                    title="Grades, models and SKUs"
                    description="Concrete manufacturer catalogue items stay separate from the generic Product."
                  />

                  {
                    manufacturerProducts.length === 0
                      ? (
                          <div className="empty-state">
                            No manufacturer-specific Product has been recorded yet.
                          </div>
                        )
                      : (
                          <div className="stack-list">
                            {
                              manufacturerProducts.map(
                                item => (
                                  <article
                                    className="record-card"
                                    key={item.id}
                                  >
                                    <div>
                                      <span className="record-code">
                                        {
                                          item.brand
                                          ?? item.manufacturerLegalName
                                        }
                                      </span>
                                      <h3>
                                        {item.name}
                                      </h3>
                                      <p>
                                        {
                                          item.description
                                          ?? "No catalogue description recorded."
                                        }
                                      </p>
                                    </div>
                                    <div className="record-meta">
                                      <span>
                                        {
                                          item.grade
                                          ? `Grade ${item.grade}`
                                          : "Grade —"
                                        }
                                      </span>
                                      <span>
                                        {
                                          item.sku
                                          ? `SKU ${item.sku}`
                                          : "SKU —"
                                        }
                                      </span>
                                      <span>
                                        {
                                          item.originCountryIso2
                                          ? `Origin ${item.originCountryIso2}`
                                          : "Origin —"
                                        }
                                      </span>
                                    </div>
                                  </article>
                                )
                              )
                            }
                          </div>
                        )
                  }

                </>
              )
            : null
        }


        {
          activeTab === "Packaging"
            ? (
                <>

                  <SectionTitle
                    kicker="PACKAGING"
                    title="Commercial packaging hierarchy"
                    description="Package types are separate from physical UOMs and can nest from primary packs into logistics units."
                  />

                  {detailLoading
                    ? (
                        <div className="empty-state">
                          Loading packaging…
                        </div>
                      )
                    : null}

                  {!detailLoading
                    && manufacturerProducts.map(
                      item => {

                        const packaging =
                          packagingByProduct[
                            item.id
                          ] ?? [];

                        return (
                          <div
                            className="subject-section"
                            key={item.id}
                          >
                            <h3>
                              {item.name}
                            </h3>
                            <p>
                              {item.manufacturerLegalName}
                            </p>

                            {
                              packaging.length === 0
                                ? (
                                    <div className="empty-state compact">
                                      No packaging recorded.
                                    </div>
                                  )
                                : (
                                    <div className="stack-list">
                                      {
                                        packaging.map(
                                          pack => (
                                            <article
                                              className="record-card"
                                              key={pack.id}
                                            >
                                              <div>
                                                <span className="record-code">
                                                  {pack.packageTypeCode}
                                                  {" · "}
                                                  {pack.packagingLevel}
                                                </span>
                                                <h3>
                                                  {pack.name}
                                                </h3>
                                              </div>
                                              <div className="record-meta">
                                                <span>
                                                  {
                                                    pack.contentQuantity
                                                    ? `${pack.contentQuantity} ${pack.contentUomCode ?? ""}`
                                                    : pack.innerPackageCount
                                                      ? `${pack.innerPackageCount} × ${pack.innerPackagingName ?? "inner package"}`
                                                      : "Content —"
                                                  }
                                                </span>
                                                <span>
                                                  {
                                                    pack.grossWeight
                                                    ? `Gross ${pack.grossWeight} ${pack.weightUomCode ?? ""}`
                                                    : "Gross —"
                                                  }
                                                </span>
                                                <span>
                                                  {
                                                    pack.isDefault
                                                      ? "Default"
                                                      : pack.sourceType
                                                  }
                                                </span>
                                              </div>
                                            </article>
                                          )
                                        )
                                      }
                                    </div>
                                  )
                            }
                          </div>
                        );

                      }
                    )
                  }

                </>
              )
            : null
        }


        {
          activeTab === "Offers"
            ? (
                <>

                  <SectionTitle
                    kicker="COMMERCIAL"
                    title="Seller offers & Incoterms"
                    description="Commercial Offers are time-bound seller propositions. Price, MOQ and Incoterms remain separate from static Product identity and statistical trade values."
                  />

                  {detailLoading
                    ? (
                        <div className="empty-state">
                          Loading commercial offers…
                        </div>
                      )
                    : null}

                  {!detailLoading
                    && manufacturerProducts.map(
                      item => {

                        const offers =
                          offersByProduct[
                            item.id
                          ] ?? [];

                        return (
                          <div
                            className="subject-section"
                            key={item.id}
                          >
                            <h3>
                              {item.name}
                            </h3>
                            <p>
                              {item.manufacturerLegalName}
                            </p>

                            {
                              offers.length === 0
                                ? (
                                    <div className="empty-state compact">
                                      No commercial offers recorded.
                                    </div>
                                  )
                                : (
                                    <div className="stack-list">
                                      {
                                        offers.map(
                                          offer => {

                                            const namedLocation =
                                              offer.namedTradeLocationName
                                              ?? offer.namedOrganizationSiteName
                                              ?? offer.namedPlaceText
                                              ?? "Named place —";

                                            const priceBasis =
                                              `${offer.currencyCode} ${offer.unitPrice.toLocaleString()} / ${offer.priceUomCode}`;

                                            const moq =
                                              offer.minimumOrderQuantity != null
                                                ? `MOQ ${offer.minimumOrderQuantity} ${offer.minimumOrderUomCode ?? ""}`
                                                : "MOQ —";

                                            return (
                                              <article
                                                className="record-card"
                                                key={offer.id}
                                              >
                                                <div>
                                                  <span className="record-code">
                                                    {offer.incotermCode}
                                                    {" · "}
                                                    {offer.incotermEdition}
                                                  </span>
                                                  <h3>
                                                    {priceBasis}
                                                  </h3>
                                                  <p>
                                                    {offer.sellerLegalName}
                                                    {
                                                      offer.buyerLegalName
                                                        ? ` → ${offer.buyerLegalName}`
                                                        : ""
                                                    }
                                                  </p>
                                                </div>

                                                <div className="record-meta">
                                                  <span>
                                                    {namedLocation}
                                                    {
                                                      offer.namedTradeLocationUnlocode
                                                        ? ` · ${offer.namedTradeLocationUnlocode}`
                                                        : ""
                                                    }
                                                  </span>
                                                  <span>
                                                    {moq}
                                                  </span>
                                                  <span>
                                                    {
                                                      offer.packagingName
                                                      ?? "Packaging —"
                                                    }
                                                  </span>
                                                  <span>
                                                    {
                                                      offer.leadTimeDays != null
                                                        ? `${offer.leadTimeDays} day lead time`
                                                        : "Lead time —"
                                                    }
                                                  </span>
                                                  <span>
                                                    {offer.status}
                                                    {" · "}
                                                    {offer.evidenceCount}
                                                    {" source "}
                                                    {
                                                      offer.evidenceCount === 1
                                                        ? "link"
                                                        : "links"
                                                    }
                                                  </span>
                                                </div>
                                              </article>
                                            );

                                          }
                                        )
                                      }
                                    </div>
                                  )
                            }
                          </div>
                        );

                      }
                    )
                  }

                </>
              )
            : null
        }


        {
          activeTab === "Landed Cost"
            ? (
                <>

                  <SectionTitle
                    kicker="COSTING"
                    title="Landed-cost scenarios"
                    description="Each scenario preserves the source Commercial Offer and adds explicit destination, FX, duty, tax and logistics assumptions without rewriting the offer."
                  />

                  {
                    landedCostScenarios.length === 0
                      ? (
                          <div className="empty-state">
                            No landed-cost scenarios recorded.
                          </div>
                        )
                      : (
                          <div className="stack-list">
                            {
                              landedCostScenarios.map(
                                scenario => {

                                  const destination =
                                    scenario.destinationTradeLocationName
                                    ?? scenario.destinationOrganizationSiteName
                                    ?? scenario.destinationPlaceText
                                    ?? scenario.destinationCountryName;

                                  const includedComponents =
                                    scenario.components.filter(
                                      component =>
                                        component.includedInOffer
                                    );

                                  const addedComponents =
                                    scenario.components.filter(
                                      component =>
                                        !component.includedInOffer
                                    );

                                  return (
                                    <article
                                      className="record-card"
                                      key={scenario.id}
                                    >
                                      <div>
                                        <span className="record-code">
                                          {scenario.incotermCode}
                                          {" · "}
                                          {scenario.incotermEdition}
                                          {" → "}
                                          {scenario.destinationCountryIso2}
                                        </span>

                                        <h3>
                                          {
                                            scenario.scenarioCurrencyCode
                                          }
                                          {" "}
                                          {
                                            scenario.landedCostTotalScenarioCurrency
                                              .toLocaleString()
                                          }
                                        </h3>

                                        <p>
                                          {
                                            scenario.sellerLegalName
                                          }
                                          {" · "}
                                          {
                                            scenario.targetQuantity
                                          }
                                          {" "}
                                          {
                                            scenario.targetUomCode
                                          }
                                          {" · "}
                                          {
                                            destination
                                          }
                                        </p>
                                      </div>

                                      <div className="record-meta">
                                        <span>
                                          Offer: {
                                            scenario.scenarioCurrencyCode
                                          } {
                                            scenario.offerAmountScenarioCurrency
                                              .toLocaleString()
                                          }
                                        </span>

                                        <span>
                                          Added: {
                                            scenario.scenarioCurrencyCode
                                          } {
                                            scenario.addedComponentTotalScenarioCurrency
                                              .toLocaleString()
                                          }
                                        </span>

                                        <span>
                                          Per {
                                            scenario.targetUomCode
                                          }: {
                                            scenario.scenarioCurrencyCode
                                          } {
                                            scenario.landedCostPerTargetUom
                                              .toLocaleString()
                                          }
                                        </span>

                                        <span>
                                          {
                                            includedComponents.length
                                          } included breakout
                                          {
                                            includedComponents.length === 1
                                              ? ""
                                              : "s"
                                          }
                                          {" · "}
                                          {
                                            addedComponents.length
                                          } added cost
                                          {
                                            addedComponents.length === 1
                                              ? ""
                                              : "s"
                                          }
                                        </span>

                                        <span>
                                          {
                                            scenario.evidenceCount
                                          } scenario source
                                          {
                                            scenario.evidenceCount === 1
                                              ? " link"
                                              : " links"
                                          }
                                        </span>
                                      </div>

                                      {
                                        scenario.components.length > 0
                                          ? (
                                              <div className="record-meta">
                                                {
                                                  scenario.components.map(
                                                    component => (
                                                      <span
                                                        key={component.id}
                                                      >
                                                        {
                                                          component.includedInOffer
                                                            ? "Included"
                                                            : "Added"
                                                        }
                                                        {": "}
                                                        {
                                                          component.componentTypeName
                                                        }
                                                        {" · "}
                                                        {
                                                          scenario.scenarioCurrencyCode
                                                        }
                                                        {" "}
                                                        {
                                                          component.amountScenarioCurrency
                                                            .toLocaleString()
                                                        }
                                                      </span>
                                                    )
                                                  )
                                                }
                                              </div>
                                            )
                                          : null
                                      }
                                    </article>
                                  );

                                }
                              )
                            }
                          </div>
                        )
                  }

                </>
              )
            : null
        }


        {
          activeTab === "Sites"
            ? (
                <>

                  <SectionTitle
                    kicker="MANUFACTURING & ORIGIN"
                    title="Operational sites"
                    description="Manufacturer country, site country and country of origin remain separate facts."
                  />

                  {detailLoading
                    ? (
                        <div className="empty-state">
                          Loading sites…
                        </div>
                      )
                    : null}

                  {!detailLoading
                    && manufacturerProducts.map(
                      item => {

                        const sites =
                          sitesByProduct[
                            item.id
                          ] ?? [];

                        return (
                          <div
                            className="subject-section"
                            key={item.id}
                          >
                            <h3>
                              {item.name}
                            </h3>
                            <p>
                              Product origin: {
                                item.originCountryName
                                ?? "not recorded"
                              }
                            </p>

                            {
                              sites.length === 0
                                ? (
                                    <div className="empty-state compact">
                                      No operational sites linked.
                                    </div>
                                  )
                                : (
                                    <div className="stack-list">
                                      {
                                        sites.map(
                                          site => (
                                            <article
                                              className="record-card"
                                              key={site.id}
                                            >
                                              <div>
                                                <span className="record-code">
                                                  {
                                                    site.relationshipType
                                                      .replaceAll(
                                                        "_",
                                                        " "
                                                      )
                                                  }
                                                </span>
                                                <h3>
                                                  {site.siteName}
                                                </h3>
                                                <p>
                                                  {site.siteOrganizationLegalName}
                                                </p>
                                              </div>
                                              <div className="record-meta">
                                                <span>
                                                  {site.siteType}
                                                </span>
                                                <span>
                                                  {
                                                    site.siteCountryName
                                                    ?? "Country —"
                                                  }
                                                </span>
                                                <span>
                                                  {site.sourceType}
                                                </span>
                                              </div>
                                            </article>
                                          )
                                        )
                                      }
                                    </div>
                                  )
                            }
                          </div>
                        );

                      }
                    )
                  }

                </>
              )
            : null
        }


        {
          activeTab === "Documents"
            ? (
                <>

                  <SectionTitle
                    kicker="DOCUMENTS"
                    title="Product evidence"
                    description="Technical, safety, quality, origin and regulatory documents with verification and provenance."
                  />

                  <div className="subject-section">
                    <h3>
                      Generic Product
                    </h3>
                    <DocumentList
                      documents={documents}
                    />
                  </div>

                  {
                    manufacturerProducts.map(
                      item => (
                        <div
                          className="subject-section"
                          key={item.id}
                        >
                          <h3>
                            {item.name}
                          </h3>
                          <DocumentList
                            documents={
                              manufacturerDocuments[
                                item.id
                              ] ?? []
                            }
                          />
                        </div>
                      )
                    )
                  }

                </>
              )
            : null
        }


        {
          activeTab === "Compliance"
            ? (
                <>

                  <SectionTitle
                    kicker="COMPLIANCE"
                    title="Frameworks and evidence"
                    description="Compliance status remains separate from the documents used to support it."
                  />

                  <div className="subject-section">
                    <h3>
                      Generic Product
                    </h3>
                    <ComplianceList
                      records={compliance}
                    />
                  </div>

                  {
                    manufacturerProducts.map(
                      item => (
                        <div
                          className="subject-section"
                          key={item.id}
                        >
                          <h3>
                            {item.name}
                          </h3>
                          <ComplianceList
                            records={
                              manufacturerCompliance[
                                item.id
                              ] ?? []
                            }
                          />
                        </div>
                      )
                    )
                  }

                </>
              )
            : null
        }


        {
          activeTab === "Counterparties"
            ? (
                <>

                  <SectionTitle
                    kicker="COUNTERPARTY INTELLIGENCE"
                    title="Product-scoped organizations"
                    description="These organizations are returned only from product-scoped company evidence, not inferred from aggregate trade statistics."
                  />

                  {
                    counterparties.length === 0
                      ? (
                          <div className="empty-state">
                            No Product-scoped counterparties have been recorded.
                          </div>
                        )
                      : (
                          <div className="stack-list">
                            {
                              counterparties.map(
                                organization => (
                                  <article
                                    className="record-card"
                                    key={organization.id}
                                  >
                                    <div>
                                      <span className="record-code">
                                        {
                                          organization.country?.iso2
                                          ?? "—"
                                        }
                                      </span>
                                      <h3>
                                        {organization.legalName}
                                      </h3>
                                      <p>
                                        {
                                          organization.roles.join(
                                            " · "
                                          )
                                        }
                                      </p>
                                    </div>
                                    <div className="record-meta">
                                      <span>
                                        {
                                          organization.matchedActivityCount
                                        } activity
                                        {
                                          organization.matchedActivityCount === 1
                                            ? ""
                                            : "ies"
                                        }
                                      </span>
                                      {
                                        organization.matchedActivities
                                          .slice(
                                            0,
                                            2
                                          )
                                          .map(
                                            activity => (
                                              <span
                                                key={activity.id}
                                              >
                                                {
                                                  activity.activityType
                                                }
                                                {
                                                  activity.marketCountry
                                                    ? ` · ${activity.marketCountry.iso2}`
                                                    : ""
                                                }
                                              </span>
                                            )
                                          )
                                      }
                                    </div>
                                  </article>
                                )
                              )
                            }
                          </div>
                        )
                  }

                </>
              )
            : null
        }

      </section>

    </main>
  );

}


function DocumentList({
  documents
}: {
  documents: ProductDocument[];
}) {

  if (
    documents.length === 0
  ) {

    return (
      <div className="empty-state compact">
        No documents recorded.
      </div>
    );

  }


  return (
    <div className="stack-list">
      {
        documents.map(
          document => (
            <article
              className="record-card"
              key={document.id}
            >
              <div>
                <span className="record-code">
                  {document.typeCode.toUpperCase()}
                </span>
                <h3>
                  {document.title}
                </h3>
                <p>
                  {
                    document.issuerLegalName
                    ?? document.fileName
                    ?? "Issuer/file not recorded"
                  }
                </p>
              </div>
              <div className="record-meta">
                <span>
                  {document.status}
                </span>
                <span>
                  {document.verificationStatus}
                </span>
                <span>
                  {
                    document.evidenceCount
                  } source link
                  {
                    document.evidenceCount === 1
                      ? ""
                      : "s"
                  }
                </span>
              </div>
            </article>
          )
        )
      }
    </div>
  );

}


function ComplianceList({
  records
}: {
  records: ComplianceRecord[];
}) {

  if (
    records.length === 0
  ) {

    return (
      <div className="empty-state compact">
        No compliance record.
      </div>
    );

  }


  return (
    <div className="stack-list">
      {
        records.map(
          record => (
            <article
              className="record-card"
              key={record.id}
            >
              <div>
                <span className="record-code">
                  {record.frameworkCode}
                </span>
                <h3>
                  {record.frameworkName}
                </h3>
                <p>
                  {
                    record.requirementCode
                    ?? record.registrationNumber
                    ?? "Framework-level record"
                  }
                </p>
              </div>
              <div className="record-meta">
                <span>
                  {record.complianceStatus}
                </span>
                <span>
                  {
                    record.jurisdictionCountryIso2
                    ?? "Global"
                  }
                </span>
                <span>
                  {record.sourceType}
                </span>
              </div>
            </article>
          )
        )
      }
    </div>
  );

}
