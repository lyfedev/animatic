import aws_cdk as cdk
from animatic_stack import AnimaticStack

app = cdk.App()

AnimaticStack(
    app,
    "AnimaticStack",
    env=cdk.Environment(
        account="339482628818",
        region="us-east-1",
    ),
)

app.synth()
