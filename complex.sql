WITH POLICY_DATA AS
(
    SELECT
        V.CONTRACT_ID,
        V.OFFER_ID,
        V.VERSION_TYPE,
        N.PRODUCT_ID,
        N.OFFER_STATUS,
        H.PLAN_ID,

        ROW_NUMBER() OVER
        (
            PARTITION BY V.CONTRACT_ID
            ORDER BY V.OFFER_ID DESC
        ) AS RN,

        COUNT(*) OVER
        (
            PARTITION BY V.CONTRACT_ID
        ) AS CONTRACT_OFFERS_COUNT

    FROM AIIC_POLICY_VERSIONS V

         INNER JOIN OFFERS_NL N
                 ON N.OFFER_ID = V.OFFER_ID

         LEFT JOIN OFFER_HEALTH_PLAN_NL H
                ON H.OFFER_ID = N.OFFER_ID

    WHERE V.VERSION_TYPE IN ('NB', 'RENEWAL', 'ENDORSEMENT')

      AND EXISTS
          (
              SELECT 1
              FROM OCP_POLICY_CONTRACTS C
              WHERE C.CONTRACT_ID = V.CONTRACT_ID
                AND C.CONTRACT_STATUS = 'I'
          )

      AND NOT EXISTS
          (
              SELECT 1
              FROM OFFER_SME_COVERS_OPTIONAL O
              WHERE O.OFFER_ID = V.OFFER_ID
                AND O.PLAN_ID = H.PLAN_ID
                AND O.COVER_CODE = 'CH_OUTPATI'
          )
),

LATEST_OFFER AS
(
    SELECT
        CONTRACT_ID,
        OFFER_ID,
        PRODUCT_ID,
        PLAN_ID,
        VERSION_TYPE,
        CONTRACT_OFFERS_COUNT
    FROM POLICY_DATA
    WHERE RN = 1
),

CONTRACT_SUMMARY AS
(
    SELECT
        P.CONTRACT_ID,
        MAX(P.OFFER_ID) AS LAST_OFFER_ID,
        MAX(P.PRODUCT_ID) AS PRODUCT_ID,
        MAX(P.PLAN_ID) AS PLAN_ID,
        COUNT(*) AS TOTAL_ROWS,

        SUM(
            CASE
                WHEN P.VERSION_TYPE = 'NB'
                THEN 1
                ELSE 0
            END
        ) AS NB_COUNT,

        SUM(
            CASE
                WHEN P.VERSION_TYPE = 'RENEWAL'
                THEN 1
                ELSE 0
            END
        ) AS RENEWAL_COUNT

    FROM POLICY_DATA P

    GROUP BY P.CONTRACT_ID

    HAVING COUNT(*) > 0
)

SELECT
    X.CONTRACT_ID,
    X.OFFER_ID,
    X.PRODUCT_ID,
    X.PLAN_ID,
    X.VERSION_TYPE,
    X.CONTRACT_OFFERS_COUNT,

    CASE
        WHEN X.CONTRACT_OFFERS_COUNT > 5
        THEN 'HIGH'
        WHEN X.CONTRACT_OFFERS_COUNT BETWEEN 2 AND 5
        THEN 'MEDIUM'
        ELSE 'LOW'
    END AS OFFER_LEVEL,

    (
        SELECT MAX(V2.OFFER_ID)
        FROM AIIC_POLICY_VERSIONS V2
        WHERE V2.CONTRACT_ID = X.CONTRACT_ID
    ) AS MAX_CONTRACT_OFFER,

    NVL
    (
        (
            SELECT COUNT(*)
            FROM OFFER_SME_COVERS_OPTIONAL OC
            WHERE OC.OFFER_ID = X.OFFER_ID
        ),
        0
    ) AS OPTIONAL_COVERS_COUNT

FROM
(
    SELECT
        L.CONTRACT_ID,
        L.OFFER_ID,
        L.PRODUCT_ID,
        L.PLAN_ID,
        L.VERSION_TYPE,
        L.CONTRACT_OFFERS_COUNT

    FROM LATEST_OFFER L

    WHERE L.PRODUCT_ID = 51

      AND
      (
            L.PLAN_ID >= 28

            OR EXISTS
               (
                   SELECT 1
                   FROM OFFER_HEALTH_PLAN_NL HP
                   WHERE HP.OFFER_ID = L.OFFER_ID
                     AND HP.PLAN_ID IN
                         (
                             SELECT DISTINCT PLAN_ID
                             FROM OFFER_HEALTH_PLAN_NL
                             WHERE PLAN_ID IS NOT NULL
                         )
               )
      )

    UNION ALL

    SELECT
        S.CONTRACT_ID,
        S.LAST_OFFER_ID,
        S.PRODUCT_ID,
        S.PLAN_ID,
        'SUMMARY' AS VERSION_TYPE,
        S.TOTAL_ROWS

    FROM CONTRACT_SUMMARY S

    WHERE S.RENEWAL_COUNT > 0

      AND S.CONTRACT_ID NOT IN
          (
              SELECT P2.CONTRACT_ID
              FROM POLICY_DATA P2
              WHERE P2.VERSION_TYPE = 'ENDORSEMENT'
                AND P2.OFFER_STATUS = 'CANCELLED'
          )
) X

WHERE
    (
        X.PRODUCT_ID = 51
        OR
        (
            X.PRODUCT_ID <> 51
            AND X.PLAN_ID IS NOT NULL
        )
    )

AND EXISTS
    (
        SELECT 1
        FROM OCP_POLICY_CONTRACTS C2
        WHERE C2.CONTRACT_ID = X.CONTRACT_ID

          AND
          (
              C2.CONTRACT_STATUS = 'I'
              OR
              (
                  C2.CONTRACT_STATUS = 'P'
                  AND X.VERSION_TYPE = 'RENEWAL'
              )
          )
    )

ORDER BY
    X.CONTRACT_ID,
    X.OFFER_ID DESC;