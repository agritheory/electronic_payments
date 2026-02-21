<!-- Copyright (c) 2025, AgriTheory and contributors
For license information, please see license.txt-->

# Using the Example Data to Experiment with Electronic Payments

<div class="byline">
  AgriTheory 2025-11-03
</div>


The Electronic Payments application comes with a `setup.py` script that is completely optional to use. If you execute the script, it populates your ERPNext site with demo business data for a fictitious company called Chelsea Fruit Co. The data enable you to experiment with and test the Electronic Payments application's functionality before installing the app into your ERPNext site.

It's recommended to install the demo data into its own site to avoid potential interference with the configuration or data in your organization's ERPNext site.

With `bench start` running in the background, run the following command to install the demo data (there are more detailed instructions in the [installation guide](../README.md) for how to set up test API keys for different providers and have the test data script automatically generate an Electronic Payments Settings document with them):

```shell
bench execute 'electronic_payments.tests.setup.before_test'
```

Refer to the [installation guide](../README.md) for detailed instructions for how to set up a bench, a new site, and installing ERPNext and the Electronic Payments application.
