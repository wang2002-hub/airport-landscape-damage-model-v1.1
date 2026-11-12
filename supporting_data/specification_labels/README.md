# Specification labels

Ev denotes event information and the event-only specification in manuscript displays. E denotes expected damage in count comparisons. EL, EB and EBL are combined specification names defined by their inputs.

Configuration files and saved numerical outputs use E for the event-only specification. The mapping in specification_labels.json connects these identifiers to display labels. E_to_EL is displayed as Ev → EL. Saved predictions, configuration keys and numeric fields retain their original identifiers. Apply this mapping only to specification labels and contrast labels. It must not be applied to expected counts, O/E ratios or mathematical expressions. The plotting module reads the retained numerical summaries and applies the display mapping without changing their contents.
