import aws_cdk as cdk
from aws_cdk import (
    aws_ecr as ecr,
    aws_s3 as s3,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_ec2 as ec2,
)
from constructs import Construct


class AnimaticStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ECR repository
        repo = ecr.Repository(
            self, "AnimaticEcr",
            repository_name="animatic-ecr",
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # S3 media bucket
        media_bucket = s3.Bucket(
            self, "AnimaticMedia",
            bucket_name=f"animatic-media-{self.account[-6:]}",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # VPC (default — 2 AZs, public + private subnets)
        vpc = ec2.Vpc(self, "AnimaticVpc", max_azs=2)

        # ECS cluster
        cluster = ecs.Cluster(
            self, "AnimaticCluster",
            cluster_name="animatic-cluster",
            vpc=vpc,
        )

        # IAM task role — S3 read/write on media bucket
        task_role = iam.Role(
            self, "AnimaticTaskRole",
            role_name="animatic-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        media_bucket.grant_read_write(task_role)

        # SSM read access for secrets
        task_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter", "ssm:GetParameters"],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/animatic/*"],
        ))

        # Fargate service behind ALB
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "AnimaticService",
            service_name="animatic-service",
            cluster=cluster,
            cpu=1024,
            memory_limit_mib=2048,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(repo, tag="latest"),
                container_port=8000,
                task_role=task_role,
                environment={
                    "ENVIRONMENT": "production",
                    "AWS_REGION": self.region,
                },
            ),
            load_balancer_name="animatic-alb",
            public_load_balancer=True,
        )

        # Health check path
        fargate_service.target_group.configure_health_check(path="/health")

        # Outputs
        cdk.CfnOutput(self, "AlbDnsName",
                      value=fargate_service.load_balancer.load_balancer_dns_name,
                      description="ALB DNS — use this as the hosted URL")
        cdk.CfnOutput(self, "EcrRepositoryUri",
                      value=repo.repository_uri,
                      description="ECR repository URI for CI/CD")
        cdk.CfnOutput(self, "MediaBucketName",
                      value=media_bucket.bucket_name,
                      description="S3 media bucket name")
