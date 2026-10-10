"""
tenantwall SQL Modifier

Uses sqlglot to parse SQL queries and inject tenant filters.
Handles complex queries: CTEs, Window Functions, UNIONs, Subqueries.
"""

import sqlglot
from sqlglot import exp
from typing import Optional, List


SUPPORTED_DIALECTS = [
    "mysql",
    "postgres",
    "oracle",
    "tsql",
    "sqlite",
    "redshift",
    "snowflake",
    "bigquery",
    "spark",
    "databricks",
]


class SqlModifier:
    def __init__(self, dialect: str = "mysql", excluded_tables: Optional[List[str]] = None):
        if dialect not in SUPPORTED_DIALECTS:
            raise ValueError(f"Unsupported dialect: {dialect}. Use one of: {SUPPORTED_DIALECTS}")
        self.dialect = dialect
        # Normalize: lowercase, strip whitespace
        self.excluded_tables = set()
        if excluded_tables:
            for table in excluded_tables:
                self.excluded_tables.add(table.strip().lower())

    def add_filter(self, sql: str, column: str, value: str) -> str:
        try:
            tree = sqlglot.parse_one(sql, dialect=self.dialect)
        except Exception as e:
            raise ValueError(f"Failed to parse SQL: {e}")

        if not isinstance(tree, (exp.Select, exp.Union, exp.With)):
            raise ValueError(f"Unsupported statement type: {type(tree).__name__}")

        self._modify_tree(tree, column, value)

        try:
            return tree.sql(dialect=self.dialect, pretty=False)
        except Exception as e:
            raise ValueError(f"Failed to generate SQL: {e}")

    def _modify_tree(self, node: exp.Expression, column: str, value: str):
        # UNION / INTERSECT / EXCEPT
        if isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            if node.left:
                self._modify_tree(node.left, column, value)
            if node.right:
                self._modify_tree(node.right, column, value)
            return

        # WITH (CTEs)
        if isinstance(node, exp.With):
            if node.this:
                self._modify_tree(node.this, column, value)
            for cte in node.expressions:
                if isinstance(cte, exp.CTE):
                    self._modify_tree(cte.this, column, value)
            return

        # SELECT
        if isinstance(node, exp.Select):
            # Process CTEs attached to this SELECT
            with_clause = node.args.get("with")
            if with_clause:
                for cte in with_clause.expressions:
                    if isinstance(cte, exp.CTE):
                        self._modify_tree(cte.this, column, value)

            if self._is_trivial_select(node):
                return

            self._add_where_filter(node, column, value)
            self._process_subqueries(node, column, value)
            self._process_from_subqueries(node, column, value)
            return

    def _is_trivial_select(self, select: exp.Select) -> bool:
        expressions = select.expressions
        if len(expressions) == 1:
            first = expressions[0]
            if isinstance(first, exp.Literal) and not first.is_string:
                return True
            if isinstance(first, exp.Null):
                return True
        return False

    def _touches_excluded_table(self, select: exp.Select) -> bool:
        """
        Check if this SELECT touches any excluded table.
        Returns True if ANY table in the FROM/JOIN clauses is excluded.
        """
        if not self.excluded_tables:
            return False

        # Check all tables directly in FROM and JOIN
        from_clause = select.args.get("from")
        if from_clause:
            for table in from_clause.find_all(exp.Table):
                if table.name.lower() in self.excluded_tables:
                    return True

        # Check JOINs
        for join in select.args.get("joins", []) or []:
            for table in join.find_all(exp.Table):
                if table.name.lower() in self.excluded_tables:
                    return True

        return False

    def _add_where_filter(self, select: exp.Select, column: str, value: str):
        # Skip if this SELECT touches an excluded table
        if self._touches_excluded_table(select):
            return

        # Skip if the filter already exists
        if self._has_filter(select, column):
            return

        condition = exp.EQ(
            this=exp.column(column),
            expression=exp.Literal.string(value),
        )

        existing_where = select.args.get("where")
        if existing_where is None:
            select.set("where", exp.Where(this=condition))
        else:
            original = existing_where.this
            if not isinstance(original, exp.Paren):
                original = exp.Paren(this=original)
            new_where = exp.And(this=original, expression=condition)
            select.set("where", exp.Where(this=new_where))

    def _has_filter(self, select: exp.Select, column: str) -> bool:
        where = select.args.get("where")
        if where is None:
            return False
        for col in where.find_all(exp.Column):
            if col.name == column:
                return True
        return False

    def _process_subqueries(self, select: exp.Select, column: str, value: str):
        for key in ("where", "having"):
            clause = select.args.get(key)
            if clause:
                for subquery in clause.find_all(exp.Subquery):
                    if subquery.this:
                        self._modify_tree(subquery.this, column, value)

        for expression in select.expressions:
            for subquery in expression.find_all(exp.Subquery):
                if subquery.this:
                    self._modify_tree(subquery.this, column, value)

    def _process_from_subqueries(self, select: exp.Select, column: str, value: str):
        from_clause = select.args.get("from")
        if from_clause:
            for subquery in from_clause.find_all(exp.Subquery):
                if subquery.this:
                    self._modify_tree(subquery.this, column, value)