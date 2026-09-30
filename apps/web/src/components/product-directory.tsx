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
  manufacturerLegalName?: string | null;
  manufacturerTradingName?: string | null;
  isActive: boolean;
};


type ProductListResponse = {
  ok: boolean;
  products: Product[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
  };
};


export function ProductDirectory() {

  const [
    products,
    setProducts
  ] =
    useState<Product[]>([]);

  const [
    search,
    setSearch
  ] =
    useState("");

  const [
    loading,
    setLoading
  ] =
    useState(true);

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


      async function load() {

        setLoading(
          true
        );

        setError(
          null
        );


        try {

          const response =
            await apiGet<ProductListResponse>(
              "/api/products?active=true&limit=100"
            );


          if (!cancelled) {

            setProducts(
              response.products
            );

          }

        }
        catch {

          if (!cancelled) {

            setError(
              "The Product API could not be reached. Start the Origin Hut API and refresh this page."
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


      void load();


      return () => {

        cancelled =
          true;

      };

    },
    []
  );


  const filtered =
    useMemo(
      () => {

        const q =
          search
            .trim()
            .toLowerCase();


        if (!q) {

          return products;

        }


        return products.filter(
          product =>
            [
              product.name,
              product.brand,
              product.sku,
              product.gtin,
              product.description,
              product.manufacturerLegalName,
              product.manufacturerTradingName
            ]
              .filter(Boolean)
              .some(
                value =>
                  String(value)
                    .toLowerCase()
                    .includes(q)
              )
        );

      },
      [
        products,
        search
      ]
    );


  return (
    <main className="shell">

      <header className="hero">

        <div>

          <p className="eyebrow">
            ORIGIN HUT
          </p>

          <h1>
            Product Trade Master
          </h1>

          <p className="hero-copy">
            Generic trade Products, manufacturer-specific grades,
            specifications, packaging, origin, documents and
            counterparty evidence — all from the canonical backend.
          </p>

        </div>

        <div className="connection-card">

          <span className="status-dot" />

          <div>
            <strong>
              API source
            </strong>
            <span>
              {API_BASE_URL}
            </span>
          </div>

        </div>

      </header>


      <section className="panel directory-panel">

        <div className="panel-heading">

          <div>

            <p className="section-kicker">
              PRODUCT DIRECTORY
            </p>

            <h2>
              Products
            </h2>

          </div>

          <div className="product-count">
            {loading
              ? "Loading"
              : `${filtered.length} shown`}
          </div>

        </div>


        <label className="search-box">

          <span>
            Search
          </span>

          <input
            value={search}
            onChange={
              event =>
                setSearch(
                  event.target.value
                )
            }
            placeholder="Name, brand, SKU, GTIN or manufacturer"
          />

        </label>


        {error
          ? (
              <div className="empty-state error-state">
                <strong>
                  API unavailable
                </strong>
                <p>
                  {error}
                </p>
              </div>
            )
          : null}


        {!error
          && loading
          ? (
              <div className="product-grid">
                {
                  Array.from(
                    {
                      length: 4
                    }
                  )
                    .map(
                      (
                        _,
                        index
                      ) => (
                        <div
                          className="product-card skeleton"
                          key={index}
                        />
                      )
                    )
                }
              </div>
            )
          : null}


        {!error
          && !loading
          && filtered.length === 0
          ? (
              <div className="empty-state">
                <strong>
                  No matching Products
                </strong>
                <p>
                  Products appear here only when returned by the
                  Origin Hut Product API.
                </p>
              </div>
            )
          : null}


        {!error
          && !loading
          && filtered.length > 0
          ? (
              <div className="product-grid">

                {
                  filtered.map(
                    product => (
                      <Link
                        className="product-card"
                        href={
                          `/products/${product.id}`
                        }
                        key={product.id}
                      >

                        <div className="product-card-top">

                          <div>

                            <p className="card-label">
                              PRODUCT
                            </p>

                            <h3>
                              {product.name}
                            </h3>

                          </div>

                          <span className="arrow">
                            ↗
                          </span>

                        </div>

                        <p className="product-description">
                          {
                            product.description
                            ?? "No description has been recorded yet."
                          }
                        </p>

                        <div className="chip-row">

                          {
                            product.brand
                              ? (
                                  <span className="chip">
                                    {product.brand}
                                  </span>
                                )
                              : null
                          }

                          {
                            product.sku
                              ? (
                                  <span className="chip">
                                    SKU {product.sku}
                                  </span>
                                )
                              : null
                          }

                          {
                            product.manufacturerLegalName
                              ? (
                                  <span className="chip">
                                    {product.manufacturerLegalName}
                                  </span>
                                )
                              : null
                          }

                        </div>

                        <span className="open-label">
                          Open Product Workbench
                        </span>

                      </Link>
                    )
                  )
                }

              </div>
            )
          : null}

      </section>

    </main>
  );

}
