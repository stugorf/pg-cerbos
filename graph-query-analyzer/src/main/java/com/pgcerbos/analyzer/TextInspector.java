package com.pgcerbos.analyzer;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

final class TextInspector {
    private TextInspector() {
    }

    record PropertyGraphMetadata(
            Set<String> nodeLabels,
            Set<String> relationshipTypes,
            int maxDepth,
            boolean hasVariableLengthPath,
            Integer limit,
            int estimatedNodes,
            List<String> pathVariables,
            List<String> parameters,
            String queryPattern
    ) {
    }

    static PropertyGraphMetadata propertyGraph(String query) {
        Set<String> nodeLabels = new LinkedHashSet<>();
        Set<String> relationshipTypes = new LinkedHashSet<>();
        List<String> pathVariables = new ArrayList<>();
        List<String> parameters = new ArrayList<>();
        List<String> tokens = tokens(query);
        Integer limit = null;
        boolean hasVariableLengthPath = false;
        int depth = 0;
        int maxDepth = 0;
        boolean inRelationship = false;

        for (int i = 0; i < query.length(); i++) {
            char current = query.charAt(i);
            if (current == '$') {
                String parameter = readIdentifier(query, i + 1);
                if (!parameter.isEmpty()) {
                    parameters.add(parameter);
                }
            }
            if (current == '[') {
                inRelationship = true;
            } else if (current == ']') {
                if (inRelationship) {
                    depth++;
                    maxDepth = Math.max(maxDepth, depth);
                }
                inRelationship = false;
            } else if (current == ',') {
                depth = 0;
            } else if (current == '*' && inRelationship) {
                hasVariableLengthPath = true;
            } else if (current == ':') {
                String label = readIdentifier(query, i + 1);
                if (!label.isEmpty()) {
                    if (inRelationship) {
                        relationshipTypes.add(label);
                    } else {
                        nodeLabels.add(label);
                    }
                }
            }
        }

        for (int i = 0; i < tokens.size() - 1; i++) {
            if ("LIMIT".equalsIgnoreCase(tokens.get(i))) {
                limit = parseInt(tokens.get(i + 1));
            }
            if ("=".equals(tokens.get(i)) && i > 0 && "(".equals(tokens.get(i + 1))) {
                pathVariables.add(tokens.get(i - 1));
            }
        }

        String queryPattern = "simple";
        if (containsWord(query, "UNION")) {
            queryPattern = "union";
        } else if (containsWord(query, "WITH")) {
            queryPattern = "with_clause";
        } else if (countWord(query, "MATCH") > 1) {
            queryPattern = "multi_match";
        } else if (!pathVariables.isEmpty()) {
            queryPattern = "path";
        }

        int estimatedNodes = limit != null ? limit : Math.max(1, nodeLabels.size() * 10);
        return new PropertyGraphMetadata(
                nodeLabels,
                relationshipTypes,
                maxDepth,
                hasVariableLengthPath,
                limit,
                estimatedNodes,
                pathVariables,
                parameters,
                queryPattern
        );
    }

    static Map<String, Object> filters(String query) {
        Map<String, Object> filters = new LinkedHashMap<>();
        putStringFilter(filters, "risk_rating", query, "risk_rating");
        putStringFilter(filters, "severity", query, "severity");
        putStringFilter(filters, "status", query, "status");
        putStringFilter(filters, "customer_team", query, "team");
        putStringFilter(filters, "customer_region", query, "region");
        putBooleanFilter(filters, "pep_flag", query, "pep_flag");
        putAmountFilter(filters, query);
        return filters;
    }

    static Set<String> sparqlPredicates(String query) {
        Set<String> predicates = new LinkedHashSet<>();
        List<String> tokens = tokens(query);
        int braceDepth = 0;
        List<String> statement = new ArrayList<>();
        for (String token : tokens) {
            if ("{".equals(token)) {
                braceDepth++;
                statement.clear();
            } else if ("}".equals(token)) {
                braceDepth = Math.max(0, braceDepth - 1);
                statement.clear();
            } else if (".".equals(token)) {
                if (braceDepth > 0 && statement.size() >= 3) {
                    String predicate = statement.get(1);
                    if (!"a".equals(predicate) && !predicate.startsWith("?")) {
                        predicates.add(predicate);
                    }
                }
                statement.clear();
            } else if (braceDepth > 0) {
                statement.add(token);
            }
        }
        return predicates;
    }

    static boolean containsWord(String text, String... words) {
        Set<String> tokenSet = new LinkedHashSet<>();
        for (String token : tokens(text)) {
            tokenSet.add(token.toUpperCase(Locale.ROOT));
        }
        for (String word : words) {
            if (tokenSet.contains(word.toUpperCase(Locale.ROOT))) {
                return true;
            }
        }
        return false;
    }

    static boolean containsWordsInOrder(String text, String... words) {
        List<String> tokens = tokens(text).stream().map(token -> token.toUpperCase(Locale.ROOT)).toList();
        int index = 0;
        for (String token : tokens) {
            if (token.equals(words[index].toUpperCase(Locale.ROOT))) {
                index++;
                if (index == words.length) {
                    return true;
                }
            }
        }
        return false;
    }

    static boolean containsAny(String text, String... values) {
        for (String value : values) {
            if (text.contains(value)) {
                return true;
            }
        }
        return false;
    }

    private static int countWord(String text, String word) {
        int count = 0;
        for (String token : tokens(text)) {
            if (word.equalsIgnoreCase(token)) {
                count++;
            }
        }
        return count;
    }

    private static void putStringFilter(Map<String, Object> filters, String target, String query, String source) {
        List<String> tokens = tokens(query);
        for (int i = 0; i < tokens.size() - 2; i++) {
            if (source.equalsIgnoreCase(tokens.get(i)) && isComparison(tokens.get(i + 1))) {
                filters.put(target, stripQuotes(tokens.get(i + 2)));
                return;
            }
        }
    }

    private static void putBooleanFilter(Map<String, Object> filters, String target, String query, String source) {
        List<String> tokens = tokens(query);
        for (int i = 0; i < tokens.size() - 2; i++) {
            if (source.equalsIgnoreCase(tokens.get(i)) && isComparison(tokens.get(i + 1))) {
                if ("true".equalsIgnoreCase(tokens.get(i + 2))) {
                    filters.put(target, true);
                    return;
                }
                if ("false".equalsIgnoreCase(tokens.get(i + 2))) {
                    filters.put(target, false);
                    return;
                }
            }
        }
    }

    private static void putAmountFilter(Map<String, Object> filters, String query) {
        List<String> tokens = tokens(query);
        for (int i = 0; i < tokens.size() - 2; i++) {
            if ("amount".equalsIgnoreCase(tokens.get(i))) {
                Double value = parseDouble(tokens.get(i + 2));
                if (value == null) {
                    continue;
                }
                switch (tokens.get(i + 1)) {
                    case ">", ">=" -> filters.put("transaction_amount_min", value);
                    case "<", "<=" -> filters.put("transaction_amount_max", value);
                    case "=", ":" -> filters.put("transaction_amount", value);
                    default -> {
                    }
                }
            }
        }
    }

    private static boolean isComparison(String token) {
        return List.of("=", ":", ">", ">=", "<", "<=", "<>", "!=").contains(token);
    }

    private static String readIdentifier(String text, int start) {
        int index = start;
        while (index < text.length() && Character.isWhitespace(text.charAt(index))) {
            index++;
        }
        if (index < text.length() && text.charAt(index) == '`') {
            int end = text.indexOf('`', index + 1);
            return end > index ? text.substring(index + 1, end) : "";
        }
        int begin = index;
        while (index < text.length()) {
            char current = text.charAt(index);
            if (!Character.isLetterOrDigit(current) && current != '_' && current != '-') {
                break;
            }
            index++;
        }
        return begin == index ? "" : text.substring(begin, index);
    }

    private static List<String> tokens(String text) {
        List<String> tokens = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean inQuote = false;
        char quote = 0;
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (inQuote) {
                current.append(ch);
                if (ch == quote) {
                    tokens.add(current.toString());
                    current.setLength(0);
                    inQuote = false;
                }
                continue;
            }
            if (ch == '\'' || ch == '"' || ch == '`') {
                flush(tokens, current);
                current.append(ch);
                quote = ch;
                inQuote = true;
                continue;
            }
            if (Character.isLetterOrDigit(ch) || ch == '_' || ch == '?' || ch == '$') {
                current.append(ch);
                continue;
            }
            flush(tokens, current);
            if (!Character.isWhitespace(ch)) {
                if ((ch == '>' || ch == '<' || ch == '!') && i + 1 < text.length() && text.charAt(i + 1) == '=') {
                    tokens.add(String.valueOf(ch) + "=");
                    i++;
                } else {
                    tokens.add(String.valueOf(ch));
                }
            }
        }
        flush(tokens, current);
        return tokens;
    }

    private static void flush(List<String> tokens, StringBuilder current) {
        if (!current.isEmpty()) {
            tokens.add(current.toString());
            current.setLength(0);
        }
    }

    private static Integer parseInt(String value) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException exc) {
            return null;
        }
    }

    private static Double parseDouble(String value) {
        try {
            return Double.parseDouble(stripQuotes(value));
        } catch (NumberFormatException exc) {
            return null;
        }
    }

    private static String stripQuotes(String value) {
        if (value == null || value.length() < 2) {
            return value;
        }
        char first = value.charAt(0);
        char last = value.charAt(value.length() - 1);
        if ((first == '\'' && last == '\'') || (first == '"' && last == '"') || (first == '`' && last == '`')) {
            return value.substring(1, value.length() - 1);
        }
        return value;
    }
}
