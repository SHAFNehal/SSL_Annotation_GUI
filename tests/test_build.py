import unittest

from build import build_arguments


class BuildTests(unittest.TestCase):
    def test_manual_excludes_ai_even_if_installed_in_build_environment(self):
        args = build_arguments()
        self.assertIn("--onefile", args)
        self.assertIn("--name=SSLAnnotationStudio", args)
        self.assertIn("--exclude-module=torch", args)
        self.assertIn("--exclude-module=transformers", args)

    def test_ai_includes_dynamic_model_imports_and_distribution_metadata(self):
        args = build_arguments(ai=True)
        for argument in ("--onedir", "--name=SSLAnnotationStudio-AI", "--collect-all=transformers",
                         "--recursive-copy-metadata=transformers", "--copy-metadata=torch",
                         "--collect-all=torchvision", "--hidden-import=src.ai_worker"):
            self.assertIn(argument, args)
        self.assertNotIn("--onefile", args)
        self.assertFalse(any(arg.startswith("--exclude-module=") for arg in args))

    def test_platform_specific_options_and_shared_icons(self):
        windows = build_arguments(ai=True, platform="win32")
        self.assertTrue(any(arg.endswith(";src/icons") for arg in windows))
        macos = build_arguments(ai=True, platform="darwin")
        self.assertIn("--osx-bundle-identifier=edu.shsu.ssl.annotationstudio.ai", macos)
        self.assertTrue(any(arg.endswith("SSL_Lab_Logo_Final.png") and arg.startswith("--icon=") for arg in windows))
        self.assertTrue(any(arg.endswith(":src/icons") for arg in macos))
